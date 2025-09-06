from typing import Callable
from uuid import uuid4
from pathlib import Path
from mimetypes import guess_type
from enum import Enum

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from rq.job import Job

from app.infrastructure.redis_client import default_queue, redis_conn
from app.infrastructure.storage import output_path, probe_any
from app.app_tasks.process import process_file_task
import logging


logger = logging.getLogger('router.file')


router = APIRouter(prefix="/files", tags=["files"])


class TaskType(str, Enum):
    image = "image"
    excel = "excel"
    excel_to_pdf = "excel_to_pdf"
    text = "text"
    baoguan = "baoguan"


DEFAULT_EXT_MAP: dict[TaskType, str] = {
    TaskType.image: "png",
    TaskType.excel: "xlsx",
    TaskType.excel_to_pdf: "pdf",
    TaskType.text: "txt",
    TaskType.baoguan: "zip",
}

WORKER_MAP: dict[TaskType, Callable] = {
    TaskType.image: process_file_task,
    TaskType.excel: process_file_task,
    TaskType.excel_to_pdf: process_file_task,
    TaskType.text: process_file_task,
    TaskType.baoguan: process_file_task,
}

@router.post("", summary="上传并排队处理")
async def upload(
    file: UploadFile = File(...),
    task_type: TaskType = Query(TaskType.text),
):
    raw = await file.read()
    task_id = uuid4().hex

    worker = WORKER_MAP.get(task_type)
    if not worker:
        raise HTTPException(status_code=400, detail=f"未知任务类型: {task_type}")

    default_ext = DEFAULT_EXT_MAP.get(task_type, "bin")

    try:
        job = default_queue.enqueue(
            worker,
            task_id,
            raw,
            task_type=task_type.value,
            ext=default_ext,
            job_id=task_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务投递失败: {e}")

    task_type_val = getattr(task_type, "value", str(task_type))
    logger.info(
        f"📥 [上传接口] 开始处理, "
        f"task_type={task_type_val}, "
        f"filename={file.filename}, "
        f"ext={default_ext}"
    )
    job.meta.update(
        {
            "task_type": task_type.value,  # 存成字符串，避免 Enum 反序列化问题
            "expect_ext": default_ext,
            "filename": file.filename,
            "content_type": file.content_type,
        }
    )
    job.save_meta()

    return {"task_id": task_id, "status": job.get_status(refresh=False)}


@router.get("/{task_id}/status", summary="查询任务状态")
def status(task_id: str):
    
    try:
        job = Job.fetch(task_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="任务不存在")

    data = {
        "task_id": task_id,
        "status": job.get_status(refresh=True),
        "result": job.result if job.is_finished else None,
        "exc_info": job.exc_info if job.is_failed else None,
        "meta": {
            "task_type": job.meta.get("task_type"),
            "output_ext": job.meta.get("output_ext"),
            "expect_ext": job.meta.get("expect_ext"),
            "filename": job.meta.get("filename"),
            "content_type": job.meta.get("content_type"),
        },
    }
    return jsonable_encoder(data)


@router.get("/{task_id}/download", summary="下载生成文件")
def download(task_id: str):
    logger.info(f"📥 [下载接口] 开始处理, task_id={task_id}")
    ext: str | None = None
    job: Job | None = None
    try:
        job = Job.fetch(task_id, connection=redis_conn)
        task_type = job.meta.get("task_type")
        logger.info(f"✅ 已获取任务: task_type={task_type}")
        if task_type:
            try:
                task_type = TaskType(task_type)  # 转换成 Enum
            except ValueError:
                task_type = None
        ext = job.meta.get("output_ext") or job.meta.get("expect_ext")
        if not ext and task_type:
            ext = DEFAULT_EXT_MAP.get(task_type)
        logger.info(f"📄 文件扩展名解析结果: {ext}")
    except Exception as e:
        logger.warning(f"⚠️ 获取任务失败: {e}")

    path: Path | None = None
    if ext:
        candidate = output_path(task_id, ext=ext)
        if candidate.exists():
            path = candidate
            logger.info(f"🔍 找到候选文件: {path}")

    if path is None:
        path = probe_any(task_id)
        logger.info(f"🔎 probe_any 查找结果: {path}")

    if path is None or not path.exists():
        logger.error(f"❌ 文件未找到, task_id={task_id}")
        raise HTTPException(status_code=404, detail="文件未找到!")

    # 优先使用原始文件名
    filename = None
    if job:
        filename = job.meta.get("filename")
    if not filename:
        filename = f"result_{task_id}{path.suffix}"
    logger.info(f"📦 最终下载文件名: {filename}")

    media_type = guess_type(path.name)[0] or "application/octet-stream"
    logger.info(f"🎉 下载成功, 返回文件: {path}")
    return FileResponse(
        str(path),
        media_type=media_type,
        filename=filename,
    )
from typing import Literal, Callable
from uuid import uuid4
from pathlib import Path
from mimetypes import guess_type

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, JSONResponse
from rq.job import Job

from app.infrastructure.redis_client import default_queue, redis_conn
from app.infrastructure.storage import output_path, probe_any
from app.app_tasks.process import process_file_task


router = APIRouter(prefix="/files", tags=["files"])


DEFAULT_EXT_MAP: dict[str, str] = {
    "image": "png",
    "excel": "xlsx",
    "excel_to_pdf": "pdf",
    "text": "txt",
}

WORKER_MAP: dict[str, Callable] = {
    "image": process_file_task,
    "excel": process_file_task,
    "excel_to_pdf": process_file_task,
    "text": process_file_task,
}

@router.post('', summary='上传并排队处理')
async def upload(
    file: UploadFile = File(...),
    task_type: Literal["image", "excel", "excel_to_pdf", "text"] = Query("text"),
):
    raw = await file.read()
    task_id = uuid4().hex
    
    worker = WORKER_MAP.get(task_type)
    if not worker:
        raise HTTPException(400, f"未知任务类型: {task_type}")
    
    default_ext = DEFAULT_EXT_MAP.get(task_type, "bin")

    job = default_queue.enqueue(
        worker,
        task_id,
        raw,
        task_type = task_type,
        ext = default_ext,
        job_id = task_id
    )
    
    job.meta["task_type"] = task_type
    job.meta["expect_ext"] = default_ext
    job.save_meta()
    return {"task_id": task_id, "status": job.get_status(refresh=False)}


@router.get("/{task_id}/status", summary="查询任务状态")
def status(task_id: str):
    try:
        job = Job.fetch(task_id, connection=redis_conn)
    except:
        raise HTTPException(404, "任务不存在")
    
    data = {
        "task_id": task_id,
        "status": job.get_status(refresh=True),
        "result": job.result if job.is_finished else None,
        "exc_info": job.exc_info if job.is_failed else None,
        "meta": {
            "task_type": job.meta.get("task_type"),
            "output_ext": job.meta.get("output_ext"),
            "expect_ext": job.meta.get("expect_ext"),
        },
    }
    return JSONResponse(data=data)



@router.get("/{task_id}/download", summary="下载生成文件")
def download(task_id: str):
    # 先从 Job.meta 拿扩展名；没有则 fallback 到默认映射；最后磁盘探测
    ext = None
    try:
        job = Job.fetch(task_id, connection=redis_conn)
        ext = job.meta.get("output_ext") or job.meta.get("expect_ext")
        if not ext:
            task_type = job.meta.get("task_type") or ""
            ext = DEFAULT_EXT_MAP.get(task_type)
    except Exception:
        pass
    
    path: Path | None = None
    if ext:
        candidate = output_path(task_id, ext=ext)
        if candidate.exists():
            path = candidate
    
    if path is None:
        path = probe_any(task_id)
        
    if path is None or not path.exists():
        raise HTTPException(404, "文件未找到!")
    
    media_type = guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        str(path),
        media_type=media_type,
        filename=f"result_{task_id}{path.suffix}",
    )
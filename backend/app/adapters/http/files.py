import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from uuid import uuid4
from rq.job import Job
from mimetypes import guess_type
from pathlib import Path

from app.infrastructure.redis import default_queue, redis_conn
from app.infrastructure.storage import output_path
from app.app_tasks.process import process_file_task


router = APIRouter(prefix="/files", tags=["files"])


@router.post("", summary="上传并排队处理")
async def upload(file: UploadFile = File(...)):
    raw = await file.read()
    task_id = uuid4().hex
    job = default_queue.enqueue(process_file_task, task_id, raw, ext='txt', job_id=task_id)
    return {'task_id': task_id, 'status': job.get_status(refresh=False)}


@router.get("/{task_id}/status", summary="查询任务状态")
def status(task_id: str):
    try:
        job = Job.fetch(task_id, connection=redis_conn)
    except:
        raise HTTPException(404, "Task not found")
    
    data = {
        'task_id': task_id,
        'status': job.get_status(refresh=True),
        "result": job.result if job.is_finished else None,
        "exc_info": job.exc_info if job.is_failed else None,
    }

    return JSONResponse(data=data)


@router.get('/{task_id}/download', summary="下载生成文件")
def download(task_id: str):
    # --------------------------------------------------------
    # 这里按你任务里 ext="txt" 来寻找目标文件；若不同类型要做映射
    # --------------------------------------------------------

    path: Path = output_path(task_id, ext="txt")
    if not path.exists():
        raise HTTPException(404, "文件未找到!")
    
    media_type = guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        str(path),
        media_type=media_type,
        filename=f"result_{task_id}{path.suffix}",
    )
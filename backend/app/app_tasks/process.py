from app.infrastructure.storage import output_path
from app.core.loggers import setup_logging
from pathlib import Path
from rq import get_current_job
import logging
# get_current_job函数的主要作用是获取当前正在执行的作业对象。
# 当一个任务被 RQ worker 执行时，可以通过这个函数获取到当前作业的详细信息。


setup_logging("INFO")  # 关键：在 worker 进程里也调用
logger = logging.getLogger("erp.worker")


def _handle_image(raw: bytes) -> bytes:
    # TODO: 替换为真实图像处理逻辑
    return raw  # 示例：当前直接回写

def _handle_excel(raw: bytes) -> bytes:
    # TODO: 生成 .xlsx
    return raw

def _handle_excel_to_pdf(raw: bytes) -> bytes:
    # TODO: excel 渲染为 pdf
    return raw

def _handle_excel_with_baoguan(raw: bytes) -> bytes:
    # TODO: excel 渲染为 pdf
    logger.info("进入_handle_excel_with_baoguan")
    return raw


def process_file_task(task_id: str, raw: bytes, task_type: str, ext: str = "txt"):
    job = get_current_job()
    logger.info(
        "进入process_file_task job/taskid=%s type=%s ext=%s",
        getattr(job, "id", None), task_type, ext
    )

    if task_type == "image":
        processed = _handle_image(raw)
        ext = "png"
    elif task_type == "excel":
        processed = _handle_excel(raw)
        ext = "xlsx"
    elif task_type == "excel_to_pdf":
        processed = _handle_excel_to_pdf(raw)
        ext = "pdf"
    elif task_type == "baoguan":
        processed = _handle_excel_with_baoguan(raw)
        ext = "zip"
    else:
        # text 默认直接落地
        processed = raw
        ext = ext or "txt"
    
    path: Path = output_path(task_id, ext=ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        logger.info('文件保存地址：%s', path.resolve())
        f.write(processed)
    
        # 回写元信息，供 /status /download 使用
    if job:
        job.meta["output_ext"] = ext
        job.save_meta()
        
    return {'path': str(path), 'ext': ext}
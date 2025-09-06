from app.infrastructure.storage import output_path
from app.core.loggers import setup_logging
from pathlib import Path
from rq import get_current_job
from datetime import datetime
import logging
# 避免同名递归：把导入的函数改名
from app.app_tasks.process_BaoGuan import _handle_excel_with_baoguan as build_baoguan_zip


setup_logging("INFO")  # 关键：在 worker 进程里也调用
logger = logging.getLogger("erp.worker")


def _handle_image(raw: bytes) -> bytes:
    logger.info("进入 _handle_image, 输入大小=%d bytes", len(raw))
    return raw

def _handle_excel(raw: bytes) -> bytes:
    logger.info("进入 _handle_excel, 输入大小=%d bytes", len(raw))
    return raw

def _handle_excel_to_pdf(raw: bytes) -> bytes:
    logger.info("进入 _handle_excel_to_pdf, 输入大小=%d bytes", len(raw))
    return raw

def _handle_excel_with_baoguan(raw: bytes) -> bytes:
    """
    Excel -> 生成5个xlsx -> 打包zip（二进制返回）
    实际工作交给 build_baoguan_zip（来自 process_BaoGuan）
    """
    logger.info("进入 _handle_excel_with_baoguan, 输入大小=%d bytes", len(raw))
    return build_baoguan_zip(raw)  # ← 调用真正实现


def process_file_task(task_id: str, raw: bytes, task_type: str, ext: str = "txt"):
    job = get_current_job()
    in_size = len(raw) if isinstance(raw, (bytes, bytearray)) else -1
    logger.info(
        "进入 process_file_task job_id=%s type=%s ext=%s in_size=%s",
        getattr(job, "id", None), task_type, ext, in_size
    )

    changes_name = None
    try:
        # ---- 分发处理 ----
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
            today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            changes_name = f"baoguan_{today_str}.zip"
            ext = "zip"
        else:
            processed = raw
            ext = ext or "txt"

        # ---- 落盘 ----
        path: Path = output_path(task_id, ext=ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(processed)
        logger.info("文件已保存: %s (size=%d)", path.resolve(), path.stat().st_size)

        # ---- 回写元信息 ----
        if job:
            job.meta["output_ext"] = ext
            if changes_name:
                job.meta["filename"] = changes_name
            job.save_meta()

        return {"path": str(path), "ext": ext}

    except Exception as e:
        # 记录异常 + 简短错误信息回写到 job.meta
        logger.exception("任务处理失败 (task_id=%s, type=%s): %s", task_id, task_type, e)
        if job:
            job.meta["error_message"] = str(e)[:500]
            job.save_meta()

        # 方案A（推荐）：重新抛出，让 RQ 标记为 failed，并保留完整 exc_info
        raise
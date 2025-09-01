from app.infrastructure.storage import output_path
from pathlib import Path
from rq import get_current_job
# get_current_job函数的主要作用是获取当前正在执行的作业对象。
# 当一个任务被 RQ worker 执行时，可以通过这个函数获取到当前作业的详细信息。

def _handle_image(raw: bytes) -> bytes:
    # TODO: 替换为真实图像处理逻辑
    return raw  # 示例：当前直接回写

def _handle_excel(raw: bytes) -> bytes:
    # TODO: 生成 .xlsx
    return raw

def _handle_excel_to_pdf(raw: bytes) -> bytes:
    # TODO: excel 渲染为 pdf
    return raw


def process_file_task(task_id: str, raw: bytes, task_type: str, ext: str = "txt"):
    """
    - task_type: "image" | "excel" | "excel_to_pdf" | "text"
    - ext: 默认扩展名（可被具体分支覆盖）
    """
    job = get_current_job()

    if task_type == "image":
        processed = _handle_image(raw)
        ext = "png"
    elif task_type == "excel":
        processed = _handle_excel(raw)
        ext = "xlsx"
    elif task_type == "excel_to_pdf":
        processed = _handle_excel_to_pdf(raw)
        ext = "pdf"
    else:
        # text 默认直接落地
        processed = raw
        ext = ext or "txt"
        
    path: Path = output_path(task_id, ext=ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(processed)
    
        # 回写元信息，供 /status /download 使用
    if job:
        job.meta["output_ext"] = ext
        job.save_meta()
        
    return {'path': str(path), 'ext': ext}
from app.infrastructure.storage import output_path, save_bytes



def process_file_task(task_id: str, raw_bytes: bytes, *, ext: str = "txt") -> str:
    """
    实际的业务处理逻辑。这里示例：简单加前缀并写入目标文件。
    你可以在这里做 CSV->XLSX、图像打包ZIP、PDF合成等。
    返回：最终文件的绝对路径字符串
    任务里用 Redis pub/sub 或写入 task:{id}:progress=0.3，状态接口返回 progress。
    """
    processed = b"Processed: " + raw_bytes
    out = output_path(task_id, ext=ext)
    save_bytes(out, processed)
    return str(out)
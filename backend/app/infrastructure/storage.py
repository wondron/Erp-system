from pathlib import Path
from app.core.config import get_settings

S = get_settings()


def ensure_task_dir(task_id: str) -> Path:
    folder = S.OUTPUT_DIR / task_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder



def output_path(task_id: str, ext: str = "bin") -> Path:
    folder = ensure_task_dir(task_id)
    return folder / f"{task_id}.{ext}"


# 在 OUTPUT_DIR/task_id/ 下按通配 task_id.* 找第一个匹配文件，找不到就返回 None。
# 用于：下载端不知道扩展名时，兜底去磁盘探测已有产物。
def probe_any(task_id: str) -> Path | None:
    folder = S.OUTPUT_DIR / task_id
    if not folder.exists():
        return None
    cands = sorted(folder.glob(f"{task_id}.*"))
    return cands[0] if cands else None


if __name__ == "__main__":
    print("hahaha")
    print(ensure_task_dir("test"))
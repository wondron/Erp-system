from pathlib import Path
from app.core.config import get_settings

S = get_settings()

def output_path(task_id: str, ext: str = "bin") -> Path:
    return Path(S.OUTPUT_DIR) / f"{task_id}.{ext}"


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
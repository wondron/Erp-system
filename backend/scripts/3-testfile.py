# client_demo.py
import os
import time
import re
import requests
from pathlib import Path

# ====== 配置区 ======
BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api"        # 如果你在 main.py 用的是 /api/v1，这里改成 "/api/v1"
FILES_BASE = f"{BASE_URL}{API_PREFIX}/files"

POLL_INTERVAL_SEC = 1.0    # 轮询间隔
POLL_TIMEOUT_SEC = 120     # 轮询超时

# ====== 小工具 ======
def _get_filename_from_cd(cd: str | None) -> str | None:
    """从 Content-Disposition 里解析 filename"""
    if not cd:
        return None
    m = re.search(r'filename\*?=(?:UTF-8\'\')?("?)([^";]+)\1', cd)
    return m.group(2) if m else None

def upload_bytes(data: bytes, filename: str, task_type: str = "text") -> str:
    """上传原始字节；也可以改成传文件路径"""
    files = {"file": (filename, data)}
    params = {"task_type": task_type}
    r = requests.post(f"{FILES_BASE}", files=files, params=params, timeout=30)
    r.raise_for_status()
    resp = r.json()
    print("Upload resp:", resp)
    return resp["task_id"]

def upload_path(path: str | os.PathLike, task_type: str = "text") -> str:
    """上传一个本地文件路径"""
    path = Path(path)
    with path.open("rb") as f:
        files = {"file": (path.name, f)}
        params = {"task_type": task_type}
        r = requests.post(f"{FILES_BASE}", files=files, params=params, timeout=60)
    r.raise_for_status()
    resp = r.json()
    print("Upload resp:", resp)
    return resp["task_id"]

def poll_status(task_id: str, timeout: int = POLL_TIMEOUT_SEC) -> dict:
    """轮询任务状态直到 finished / failed / 超时"""
    start = time.time()
    url = f"{FILES_BASE}/{task_id}/status"
    terminal = {"finished", "failed", "stopped", "canceled"}  # RQ 终态
    while True:
        r = requests.get(url, timeout=10)
        if r.status_code == 404:
            raise RuntimeError("任务不存在（404）")
        r.raise_for_status()
        data = r.json()
        status = (data.get("status") or "").lower()
        print(f"[{time.time()-start:5.1f}s] status = {status}")
        if status in terminal:
            return data
        if time.time() - start > timeout:
            raise TimeoutError("轮询超时")
        time.sleep(POLL_INTERVAL_SEC)

def download_result(task_id: str, save_dir: str | os.PathLike = "downloads") -> Path:
    """下载产物到本地目录，并返回保存路径"""
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    url = f"{FILES_BASE}/{task_id}/download"
    with requests.get(url, stream=True, timeout=60) as r:
        if r.status_code != 200:
            print("Download failed:", r.status_code, r.text)
            r.raise_for_status()
        cd = r.headers.get("Content-Disposition")
        fname = _get_filename_from_cd(cd) or f"result_{task_id}"
        out = Path(save_dir) / fname
        with out.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print("Saved to:", out)
    return out

# ====== Demo 入口 ======
if __name__ == "__main__":
    # 1) 选一个任务类型：text / image / excel / excel_to_pdf
    TASK_TYPE = "text"

    # 2A) 直接上传一些字节数据（最省事）
    task_id = upload_bytes(b"hello from client_demo", "hello.txt", task_type=TASK_TYPE)

    # 2B) 或者：上传本地文件（取消注释）
    # task_id = upload_path("README.md", task_type=TASK_TYPE)

    # 3) 轮询状态
    info = poll_status(task_id)
    print("Final status payload:", info)

    # 4) 下载结果文件
    download_result(task_id)

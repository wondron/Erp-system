cd backend
#windows
set PYTHONPATH=%cd%
# macos Linux
export PYTHONPATH=$(pwd)
python scripts/db_smoketest.py


set PYTHONPATH=%cd%
意思是：把当前目录 (%cd% 在 Windows 下代表“当前路径”) 临时加入到 Python 的模块搜索路径 PYTHONPATH 环境变量里。
backend/
  app/
    infrastructure/db.py
    core/config.py
    ...
当你在 backend/ 目录里运行 python scripts/db_smoketest.py 的时候，Python 默认只会把 backend/ 放到 sys.path，但是它未必能正确识别 app 作为一个顶级包。
设置 PYTHONPATH=%cd% 以后，Python 会把当前目录（backend/）加入到 sys.path，这样就能在脚本里写：

from app.core.config import get_settings
from app.infrastructure.db import SessionLocal


否则可能会报错：ModuleNotFoundError: No module named 'app'。
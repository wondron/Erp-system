@echo off
REM ========================
REM RQ Worker 启动脚本 (CMD 版)
REM 读取 .env.dev -> 设置环境变量 -> 启动 rq worker
REM ========================

setlocal EnableExtensions EnableDelayedExpansion

REM 切换到脚本所在目录（通常是 backend/）
cd /d "%~dp0"

if not exist ".env.dev" (
  echo [ERROR] .env.dev not found in %CD%
  pause
  exit /b 1
)

REM 逐行读取 .env.dev：# 开头为注释；按 = 切分为 KEY / VALUE
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env.dev") do (
  set "K=%%A"
  set "V=%%B"

  REM 去掉 KEY 前后的空格（VALUE 通常不处理，避免破坏内容）
  for /f "tokens=* delims= " %%i in ("!K!") do set "K=%%i"

  REM 支持 'export KEY=VALUE' 风格
  if /i "!K:~0,7!"=="export " set "K=!K:~7!"
  for /f "tokens=* delims= " %%i in ("!K!") do set "K=%%i"

  if not "!K!"=="" (
    set "!K!=!V!"
  )
)

echo REDIS_URL  = %REDIS_URL%
echo OUTPUT_DIR = %OUTPUT_DIR%
echo.
echo Starting RQ worker...

REM -u 用引号更安全；-P 用当前目录
rq worker -u "%REDIS_URL%" default --worker-class rq.SimpleWorker -P "%CD%"

endlocal
pause
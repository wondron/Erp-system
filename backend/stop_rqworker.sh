cd /data/Erp-system/backend

# 1) 让管理器收到“停止指令”，避免它把子进程又拉起来
touch rqworker.stop

# 2) 优雅停止：先给子进程（rq worker）发 INT，再给管理器发 TERM
kill -INT 381989 2>/dev/null || true
kill -TERM 381828 2>/dev/null || true

# 3) 等 3 秒观察
sleep 3
ps -p 381828 381989 -o pid,ppid,cmd

# 4) 还活着就递进强制：先杀子，再杀父；顺带清掉父进程的所有子孙
pkill -TERM -P 381828 2>/dev/null || true
sleep 1
pkill -KILL -P 381828 2>/dev/null || true
kill -KILL 381989 2>/dev/null || true
kill -KILL 381828 2>/dev/null || true

# 5) 清理残留标记，防止“僵尸文件”影响再次启动
rm -f rqworker_manager.pid rqworker.pid rqworker.stop

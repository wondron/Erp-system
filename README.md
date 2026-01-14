## 本地开发
1. requirement 安装
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirement.txt
```

2. 启动数据库与 Redis
使用 docker-compose-dev.yml 启动
```bash
docker compose -f docker-compose.yml up -d
```

3. 初始化数据库（Alembic）
```linux
cd /data/Erp-system/backend
export PYTHONPATH=$(pwd)
export DATABASE_URL_YIBU='postgresql+asyncpg://kumori:123456@localhost:5432/erpdb'
export sqlalchemy_database_asyn_uri=$DATABASE_URL_YIBU
alembic upgrade head
```

``` windows cmd
cd backend
set PYTHONPATH=%cd%
set DATABASE_URL_YIBU=postgresql+asyncpg://kumori:123456@127.0.0.1:5432/erpdb
set sqlalchemy_database_asyn_uri=%DATABASE_URL_YIBU%
alembic upgrade head
```


```bash
cd backend
set -a; source .env.dev; set +a   # Windows 可用: setx /M ... 或临时在 PowerShell $env:VAR=...
alembic upgrade head
```
看到 Context impl PostgresqlImpl、Running upgrade ... 就是 OK。


4. 启动 API 和 RQ Worker
两个终端分别执行：
```bash
# 终端2：RQ Worker
# 1) 环境变量（Linux 用 export 和 $VAR）
export PROJECT_ROOT=/data/Erp-system/backend
export PYTHONPATH="$PROJECT_ROOT"
export PYTHONUNBUFFERED=1
export REDIS_URL=redis://localhost:6379/0    # 或者你的 redis 地址

# 2) 进入项目目录
cd "$PROJECT_ROOT"

# 3) （可选）激活 conda 环境
# eval "$(/root/miniconda3/bin/conda shell.bash hook)"   # 如果还没 init
# conda activate erp

# 4) 启动 RQ Worker
rq worker -u "$REDIS_URL" default \
  --worker-class rq.SimpleWorker \
  -P "$PROJECT_ROOT"
```

# windows cmd:（不带env参数）
# 终端1：FastAPI
cd /d D:\01-code\Erp-system\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

``` bash
set PROJECT_ROOT=D:\01-code\Erp-system\backend
set PYTHONPATH=%PROJECT_ROOT%
set PYTHONUNBUFFERED=1
set REDIS_URL=redis://localhost:6379/0
cd /d %PROJECT_ROOT%
rq worker -u %REDIS_URL% default --worker-class rq.SimpleWorker -P %PROJECT_ROOT%
```


# 启动fastapi
``` bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

nohup uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  > uvicorn.log 2>&1 &

```



# 一键启动（服务器）
1. 启动
>docker compose --env-file .env.prod -f docker-compose-prod.yml up -d
2. 查看状态，端口有没有开启
docker compose --env-file .env.prod -f docker-compose-prod.yml ps

正常状态是：
```bash
NAME           IMAGE                COMMAND                   SERVICE    CREATED         STATUS                    PORTS
erp-backend    backend-backend      "sh -c ' alembic upg…"   backend    4 seconds ago   Up Less than a second     0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
erp-postgres   postgres:16-alpine   "docker-entrypoint.s…"   postgres   24 hours ago    Up 15 minutes (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
erp-redis      redis:7-alpine       "docker-entrypoint.s…"   redis      24 hours ago    Up 15 minutes (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
erp-worker     backend-worker       "rq worker -u redis:…"   worker     4 seconds ago   Up 4 seconds
```

3. 查看日志：
docker compose -f docker-compose-prod.yml logs backend
docker compose -f docker-compose-prod.yml logs -f backend worker postgres

4. 常用的命令
| 功能             | 命令                                   |
| -------------- | ------------------------------------ |
| 查看正在运行的容器      | `docker ps`                          |
| 查看所有容器（包括已退出的） | `docker ps -a`                       |
| 启动容器           | `docker start <容器名/ID>`              |
| 停止容器           | `docker stop <容器名/ID>`               |
| 重启容器           | `docker restart <容器名/ID>`            |
| 删除容器           | `docker rm <容器名/ID>`                 |
| 进入容器           | `docker exec -it <容器名> bash`（或 `sh`） |
| 退出容器终端         | `exit` 或 `Ctrl+D`                    |



  {
    "销售信息": {
      "大类目": "家居",
      "小品类": "家居服",
      "季节性": "冬季",
      "产品": "Kumori-法莱绒家居服（老款）-灰M",
      "销售渠道": "VC",
      "责任人": "周叶鲁",
      "SKU": "810101409417",
      "ASIN": "B0DCB7VVZW",
      "产品条码": "810101409417",
      "自定义箱唛": "FLRJJF-HS-M",
      "货号": "SG-MH-KM-F",
      "颜色": "アイボリー",
      "尺寸": "M",
      "销售价": 2980
    },
    "供应信息": {
      "供应商": "常熟市新韵纺织品有限公司",
      "采购价": 43,
      "单品包装尺寸": "35*25*10",
      "单品包装重量": 0.85,
      "装箱系数": 20,
      "外箱长": 65,
      "外箱宽": 53,
      "外箱高": 38
    },
    "报关信息": {
      "中文品名": "家居服",
      "英文品名": "Roomwear",
      "海关编码": "6108320000",
      "申报要素": "1|0|针织印花|家居服|男女通用|100%聚酯纤维|无中文品牌Kumori",
      "申报价": 860,
      "图片": "另外上传"
    },
    "生产配套": {
      "材料1": "300g双面法莱绒\\205cm\\半消光\\有导电丝\\满穿-灰",
      "材料1用量": 0.95,
      "材料2": "洗标",
      "材料2用量": 1,
      "材料3": "树脂扣-白色",
      "材料3用量": 5,
      "材料4": "【極暖】彩卡",
      "材料4用量": 1,
      "材料5": "【NL】印花拉链袋-30＊40",
      "材料5用量": 1
    }
  }



  ## 最新方法
  1. 先验证能拉镜像（很关键）：
      docker pull python:3.11-slim

  2. Dockerfile（后端镜像）准备
      FROM docker.m.daocloud.io/library/python:3.11-slim-bookworm

  3. 构建镜像（最稳方式：关 BuildKit）
      docker compose build --no-cache --progress plain

  4. 启动
      docker compose up -d
      docker compose ps
      docker compose restart

  5. 看日志排障（最常用）
    docker compose logs -f backend
    docker compose logs -f worker
    docker compose logs -f postgres
    docker exec -it erp-postgres psql -U kumori -d erpdb    # 数据库配置是否正确

    DROP TABLE IF EXISTS erp_product.material_usage CASCADE;   #清除数据

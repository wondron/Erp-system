from redis import Redis
from rq import Queue
from app.core.config import get_settings


_settings = get_settings()

redis_conn = Redis.from_url(_settings.REDIS_URL)
default_queue = Queue(connection=redis_conn)



if __name__ == '__main__':
    print(_settings.REDIS_URL)
    print("Ping:", redis_conn.ping())
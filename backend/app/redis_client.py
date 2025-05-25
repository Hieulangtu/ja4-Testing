# import redis.asyncio as redis

# # Tạo client kết nối tới Redis; đảm bảo Redis server đang chạy
# redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

import os, re
import redis.asyncio as redis
from urllib.parse import urlparse

url = os.getenv("REDIS_URL", "redis://redis:6379/0")
parsed = urlparse(url)
db_idx = int(parsed.path.lstrip("/") or 0)

redis_client = redis.Redis(
    host=parsed.hostname,
    port=parsed.port,
    db=db_idx,
    password=parsed.password,
    decode_responses=True,
)
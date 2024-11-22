from decouple import config
import redis

redis_url = config("REDIS_URL")
redis_conn = redis.asyncio.Redis.from_url(redis_url, decode_responses=True)



import asyncio
import os
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

# Example: redis://:your_strong_password@redis:6379/0
redis_url = f'redis://:{os.getenv("REDIS_PASSWORD", None)}@{os.getenv("REDIS_HOST", "localhost")}:{os.getenv("REDIS_PORT", 6379)}/{os.getenv("REDIS_DB", 0)}'
print(f"redis url: {redis_url}")

# Create the pool directly from the URL
pool = redis.ConnectionPool.from_url(
    redis_url,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30,
)


redis_client = redis.Redis(connection_pool=pool)

async def check_redis_connection():
    """Test connection to Redis and log if it fails."""
    try:
        pong = await redis_client.ping()
        if pong:
            logging.info("Connected to Redis successfully.")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise  # Re-raise so the app fails fast instead of silently continuing

# Example use
if __name__ == "__main__":
    asyncio.run(check_redis_connection())
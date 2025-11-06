import asyncio
import os
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD", None),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30
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
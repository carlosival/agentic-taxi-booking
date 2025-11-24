
from minio import Minio
import os
import asyncio
import logging

# Environment-driven config (recommended for Docker)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Create a single MinIO client instance at import time
minio_client = Minio(
    endpoint=MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

async def test_minio_connection_async() -> bool:
    """
    Asynchronous wrapper for testing MinIO connection.
    Uses a thread to avoid blocking the event loop.
    """
    try:
        await asyncio.to_thread(minio_client.list_buckets)
        return True
    except Exception as e:
        logging.error(f"MinIO async connection failed: {e}")
        raise

# Example use
if __name__ == "__main__":
    asyncio.run(test_minio_connection_async())
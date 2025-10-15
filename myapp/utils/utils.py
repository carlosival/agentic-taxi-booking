import os

def get_secret(name: str, default: str | None = None) -> str | None:
    """
    Reads a secret from Docker secrets if available,
    otherwise falls back to a normal environment variable.
    """
    file_path = os.getenv(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip()
    return os.getenv(name, default)
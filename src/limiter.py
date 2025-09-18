from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["50000 per day", "1000 per hour"],
    storage_uri="memcached://127.0.0.1:11221",
    in_memory_fallback_enabled=True
)
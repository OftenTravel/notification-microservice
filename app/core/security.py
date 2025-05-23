import hashlib
import hmac
from app.core.config import settings


def encrypt_api_key(api_key: str) -> str:
    """
    Hash an API key using HMAC-SHA256.
    
    Args:
        api_key: The raw API key to hash
        
    Returns:
        str: The hashed API key
    """
    key = settings.API_KEY_SALT.encode()
    return hmac.new(key, api_key.encode(), hashlib.sha256).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        api_key: The raw API key to verify
        stored_hash: The previously stored hash to compare against
        
    Returns:
        bool: True if the API key is valid
    """
    calculated_hash = encrypt_api_key(api_key)
    return hmac.compare_digest(calculated_hash, stored_hash)

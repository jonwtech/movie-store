"""
Redis cache service
"""
import json
import logging
from typing import Optional, Any
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class CacheService:
    """Redis cache service"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.client = redis.from_url(
                self.config.url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            await self.client.ping()
            logger.info("✅ Redis cache connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis cache disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if not self.client:
                return None
                
            value = await self.client.get(key)
            if value is None:
                return None
                
            return json.loads(value)
            
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            if not self.client:
                return False
                
            ttl = ttl or self.config.ttl_seconds
            serialized = json.dumps(value, default=str)
            
            await self.client.setex(key, ttl, serialized)
            return True
            
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if not self.client:
                return False
                
            result = await self.client.delete(key)
            return result > 0
            
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            if not self.client:
                return 0
                
            keys = await self.client.keys(pattern)
            if keys:
                return await self.client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.warning(f"Cache pattern invalidation error for {pattern}: {str(e)}")
            return 0
    
    async def health_check(self) -> bool:
        """Check Redis health"""
        try:
            if not self.client:
                return False
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return False
    
    def cache_key(self, prefix: str, *args) -> str:
        """Generate cache key"""
        return f"{prefix}:" + ":".join(str(arg) for arg in args)
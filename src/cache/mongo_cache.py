"""
MongoDB Cache Manager for Jira Allocation Connector.

This module provides persistent caching functionality using MongoDB
for storing data with TTL-based expiration.
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
import fnmatch

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Try to import pymongo
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False
    logger.warning("pymongo_not_installed", message="MongoDB cache disabled - pymongo not installed")


class MongoCacheManager:
    """
    Manages persistent cache using MongoDB.
    
    Cache entries are stored in a MongoDB collection with TTL index
    for automatic expiration. Data is serialized using pickle for
    flexibility in storing complex Python objects.
    """
    
    DEFAULT_TTL_SECONDS = 3600  # 1 hour
    COLLECTION_NAME = "cache_entries"
    
    _client: Optional["MongoClient"] = None
    _db = None
    _collection = None
    _initialized = False
    _enabled = False
    
    @classmethod
    def initialize(cls) -> bool:
        """
        Initialize MongoDB connection.
        
        Returns:
            True if connection successful, False otherwise.
        """
        if cls._initialized:
            return cls._enabled
        
        cls._initialized = True
        
        # Check if MongoDB is enabled
        mongodb_enabled = os.getenv("MONGODB_CACHE_ENABLED", "false").lower() == "true"
        if not mongodb_enabled:
            logger.info("mongodb_cache_disabled", message="MongoDB cache disabled by configuration")
            cls._enabled = False
            return False
        
        if not HAS_PYMONGO:
            logger.warning("mongodb_unavailable", message="pymongo not installed")
            cls._enabled = False
            return False
        
        # Get connection URI
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            logger.warning("mongodb_uri_missing", message="MONGODB_URI not configured")
            cls._enabled = False
            return False
        
        # Get database name
        database_name = os.getenv("MONGODB_DATABASE", "jira_cache")
        
        try:
            # Connect to MongoDB
            cls._client = MongoClient(
                mongodb_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            
            # Test connection
            cls._client.admin.command('ping')
            
            # Get database and collection
            cls._db = cls._client[database_name]
            cls._collection = cls._db[cls.COLLECTION_NAME]
            
            # Create TTL index for automatic expiration
            cls._collection.create_index("expires_at", expireAfterSeconds=0)
            
            # Create index on key for fast lookups
            cls._collection.create_index("key", unique=True)
            
            cls._enabled = True
            logger.info("mongodb_connected", database=database_name, collection=cls.COLLECTION_NAME)
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error("mongodb_connection_failed", error=str(e))
            cls._enabled = False
            return False
        except Exception as e:
            logger.error("mongodb_init_error", error=str(e))
            cls._enabled = False
            return False
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if MongoDB cache is enabled and connected."""
        if not cls._initialized:
            cls.initialize()
        return cls._enabled
    
    @classmethod
    def get_cached_data(cls, key: str) -> Optional[Any]:
        """
        Retrieve data from MongoDB if valid (not expired).
        
        Args:
            key: The cache key to retrieve.
            
        Returns:
            The cached data if valid, None if not found or expired.
        """
        if not cls.is_enabled():
            return None
        
        try:
            doc = cls._collection.find_one({"key": key})
            
            if not doc:
                return None
            
            # Check if expired (MongoDB TTL may have slight delay)
            if datetime.utcnow() >= doc["expires_at"]:
                cls._collection.delete_one({"key": key})
                return None
            
            # Deserialize data
            return pickle.loads(doc["data"])
            
        except Exception as e:
            logger.warning("mongodb_get_error", key=key, error=str(e))
            return None
    
    @classmethod
    def get_stale_data(cls, key: str) -> Optional[Any]:
        """
        Retrieve data from MongoDB even if expired (for fallback scenarios).
        
        Args:
            key: The cache key to retrieve.
            
        Returns:
            The cached data regardless of expiration, None if not found.
        """
        if not cls.is_enabled():
            return None
        
        try:
            doc = cls._collection.find_one({"key": key})
            
            if not doc:
                return None
            
            return pickle.loads(doc["data"])
            
        except Exception as e:
            logger.warning("mongodb_get_stale_error", key=key, error=str(e))
            return None
    
    @classmethod
    def set_cached_data(cls, key: str, data: Any, ttl_seconds: int = None) -> bool:
        """
        Store data in MongoDB with expiration timestamp.
        
        Args:
            key: The cache key to store under.
            data: The data to cache.
            ttl_seconds: Time-to-live in seconds.
            
        Returns:
            True if stored successfully, False otherwise.
        """
        if not cls.is_enabled():
            return False
        
        if ttl_seconds is None:
            ttl_seconds = cls.DEFAULT_TTL_SECONDS
        
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            doc = {
                "key": key,
                "data": pickle.dumps(data),
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                "ttl_seconds": ttl_seconds
            }
            
            # Upsert - update if exists, insert if not
            cls._collection.replace_one(
                {"key": key},
                doc,
                upsert=True
            )
            
            logger.debug("mongodb_cache_set", key=key, ttl=ttl_seconds)
            return True
            
        except Exception as e:
            logger.warning("mongodb_set_error", key=key, error=str(e))
            return False
    
    @classmethod
    def is_cache_valid(cls, key: str) -> bool:
        """
        Check if cache entry is still valid based on TTL.
        
        Args:
            key: The cache key to check.
            
        Returns:
            True if entry exists and has not expired, False otherwise.
        """
        if not cls.is_enabled():
            return False
        
        try:
            doc = cls._collection.find_one(
                {"key": key, "expires_at": {"$gt": datetime.utcnow()}},
                {"_id": 1}
            )
            return doc is not None
            
        except Exception as e:
            logger.warning("mongodb_valid_check_error", key=key, error=str(e))
            return False
    
    @classmethod
    def invalidate_cache(cls, pattern: str = "*") -> int:
        """
        Invalidate cache entries matching the pattern.
        
        Args:
            pattern: Glob pattern to match keys (default: "*" matches all).
            
        Returns:
            Number of entries removed.
        """
        if not cls.is_enabled():
            return 0
        
        try:
            if pattern == "*":
                # Delete all
                result = cls._collection.delete_many({})
            else:
                # Convert glob pattern to regex
                regex_pattern = fnmatch.translate(pattern)
                result = cls._collection.delete_many({"key": {"$regex": regex_pattern}})
            
            logger.info("mongodb_cache_invalidated", pattern=pattern, count=result.deleted_count)
            return result.deleted_count
            
        except Exception as e:
            logger.warning("mongodb_invalidate_error", pattern=pattern, error=str(e))
            return 0
    
    @classmethod
    def clear_all(cls) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries removed.
        """
        return cls.invalidate_cache("*")
    
    @classmethod
    def get_cache_stats(cls) -> dict:
        """
        Get statistics about the current cache state.
        
        Returns:
            Dictionary with cache statistics.
        """
        if not cls.is_enabled():
            return {
                "enabled": False,
                "total_entries": 0,
                "valid_entries": 0,
                "expired_entries": 0
            }
        
        try:
            now = datetime.utcnow()
            
            total = cls._collection.count_documents({})
            valid = cls._collection.count_documents({"expires_at": {"$gt": now}})
            expired = total - valid
            
            return {
                "enabled": True,
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": expired
            }
            
        except Exception as e:
            logger.warning("mongodb_stats_error", error=str(e))
            return {
                "enabled": True,
                "error": str(e),
                "total_entries": 0,
                "valid_entries": 0,
                "expired_entries": 0
            }
    
    @classmethod
    def close(cls):
        """Close MongoDB connection."""
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None
            cls._collection = None
            cls._initialized = False
            cls._enabled = False
            logger.info("mongodb_connection_closed")

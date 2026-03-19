"""
Cache Manager for Jira Allocation Connector.

This module provides caching functionality with MongoDB as primary storage
and Streamlit's session_state as fallback.
"""

from datetime import datetime, timedelta
from typing import Any, Callable, Optional
import fnmatch

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

from src.models.data_models import CacheEntry
from src.cache.mongo_cache import MongoCacheManager


# Cache key prefix to avoid conflicts with other session_state keys
CACHE_PREFIX = "cache_"


class CacheManager:
    """
    Manages cache with MongoDB as primary storage and session_state as fallback.
    
    The cache manager automatically uses MongoDB if configured and available,
    otherwise falls back to Streamlit's session_state for in-memory caching.
    """
    
    DEFAULT_TTL_SECONDS = 3600  # 1 hour (increased for MongoDB persistence)
    
    @staticmethod
    def _get_cache_key(key: str) -> str:
        """Generate prefixed cache key."""
        return f"{CACHE_PREFIX}{key}"
    
    @staticmethod
    def _get_session_state() -> dict:
        """
        Get the session state storage.
        Returns st.session_state if Streamlit is available, otherwise a fallback dict.
        """
        if HAS_STREAMLIT:
            return st.session_state
        # Fallback for testing without Streamlit
        if not hasattr(CacheManager, '_fallback_state'):
            CacheManager._fallback_state = {}
        return CacheManager._fallback_state
    
    @staticmethod
    def _use_mongodb() -> bool:
        """Check if MongoDB should be used."""
        return MongoCacheManager.is_enabled()
    
    @staticmethod
    def get_cached_data(key: str) -> Optional[Any]:
        """
        Retrieve data from cache if valid (not expired).
        
        Uses MongoDB if available, otherwise session_state.
        
        Args:
            key: The cache key to retrieve.
            
        Returns:
            The cached data if valid, None if not found or expired.
        """
        # Try MongoDB first
        if CacheManager._use_mongodb():
            data = MongoCacheManager.get_cached_data(key)
            if data is not None:
                return data
        
        # Fallback to session_state
        cache_key = CacheManager._get_cache_key(key)
        state = CacheManager._get_session_state()
        
        if cache_key not in state:
            return None
        
        entry: CacheEntry = state[cache_key]
        
        # Check if entry has expired
        if datetime.now() >= entry.expires_at:
            # Remove expired entry
            del state[cache_key]
            return None
        
        return entry.data
    
    @staticmethod
    def get_stale_data(key: str) -> Optional[Any]:
        """
        Retrieve data from cache even if expired (for fallback scenarios).
        
        Args:
            key: The cache key to retrieve.
            
        Returns:
            The cached data regardless of expiration, None if not found.
        """
        # Try MongoDB first
        if CacheManager._use_mongodb():
            data = MongoCacheManager.get_stale_data(key)
            if data is not None:
                return data
        
        # Fallback to session_state
        cache_key = CacheManager._get_cache_key(key)
        state = CacheManager._get_session_state()
        
        if cache_key not in state:
            return None
        
        entry: CacheEntry = state[cache_key]
        return entry.data
    
    @staticmethod
    def set_cached_data(key: str, data: Any, ttl_seconds: int = None) -> None:
        """
        Store data in cache with expiration timestamp.
        
        Stores in both MongoDB (if available) and session_state.
        
        Args:
            key: The cache key to store under.
            data: The data to cache.
            ttl_seconds: Time-to-live in seconds.
        """
        if ttl_seconds is None:
            ttl_seconds = CacheManager.DEFAULT_TTL_SECONDS
        
        # Store in MongoDB if available
        if CacheManager._use_mongodb():
            MongoCacheManager.set_cached_data(key, data, ttl_seconds)
        
        # Also store in session_state for fast access
        cache_key = CacheManager._get_cache_key(key)
        state = CacheManager._get_session_state()
        
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        entry = CacheEntry(
            data=data,
            expires_at=expires_at,
            created_at=datetime.now()
        )
        
        state[cache_key] = entry
    
    @staticmethod
    def is_cache_valid(key: str) -> bool:
        """
        Check if cache entry is still valid based on TTL.
        
        Args:
            key: The cache key to check.
            
        Returns:
            True if entry exists and has not expired, False otherwise.
        """
        # Check MongoDB first
        if CacheManager._use_mongodb():
            if MongoCacheManager.is_cache_valid(key):
                return True
        
        # Check session_state
        cache_key = CacheManager._get_cache_key(key)
        state = CacheManager._get_session_state()
        
        if cache_key not in state:
            return False
        
        entry: CacheEntry = state[cache_key]
        return datetime.now() < entry.expires_at
    
    @staticmethod
    def invalidate_cache(pattern: str = "*") -> int:
        """
        Invalidate cache entries matching the pattern.
        
        Args:
            pattern: Glob pattern to match keys (default: "*" matches all).
            
        Returns:
            Number of entries removed.
        """
        count = 0
        
        # Invalidate in MongoDB
        if CacheManager._use_mongodb():
            count += MongoCacheManager.invalidate_cache(pattern)
        
        # Invalidate in session_state
        state = CacheManager._get_session_state()
        
        keys_to_remove = []
        for key in list(state.keys()):
            if key.startswith(CACHE_PREFIX):
                original_key = key[len(CACHE_PREFIX):]
                if fnmatch.fnmatch(original_key, pattern):
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del state[key]
        
        count += len(keys_to_remove)
        return count
    
    @staticmethod
    def get_or_fetch(
        key: str,
        fetch_fn: Callable[[], Any],
        ttl_seconds: int = None
    ) -> Any:
        """
        Return cached data if valid, otherwise execute fetch_fn and cache result.
        
        Args:
            key: The cache key.
            fetch_fn: Callable that returns fresh data when cache is invalid.
            ttl_seconds: Time-to-live in seconds for the cached data.
            
        Returns:
            The cached or freshly fetched data.
        """
        if ttl_seconds is None:
            ttl_seconds = CacheManager.DEFAULT_TTL_SECONDS
        
        # Try to get from cache first
        cached_data = CacheManager.get_cached_data(key)
        if cached_data is not None:
            return cached_data
        
        # Cache miss - fetch fresh data
        fresh_data = fetch_fn()
        
        # Store in cache
        CacheManager.set_cached_data(key, fresh_data, ttl_seconds)
        
        return fresh_data
    
    @staticmethod
    def get_or_fetch_with_fallback(
        key: str,
        fetch_fn: Callable[[], Any],
        ttl_seconds: int = None
    ) -> tuple[Any, bool]:
        """
        Return cached data if valid, otherwise fetch with fallback to stale cache on error.
        
        Args:
            key: The cache key.
            fetch_fn: Callable that returns fresh data when cache is invalid.
            ttl_seconds: Time-to-live in seconds for the cached data.
            
        Returns:
            Tuple of (data, is_stale) where is_stale indicates if data is from expired cache.
            
        Raises:
            Exception: If fetch fails and no cached data is available.
        """
        if ttl_seconds is None:
            ttl_seconds = CacheManager.DEFAULT_TTL_SECONDS
        
        # Try to get from valid cache first
        cached_data = CacheManager.get_cached_data(key)
        if cached_data is not None:
            return cached_data, False
        
        # Cache miss - try to fetch fresh data
        try:
            fresh_data = fetch_fn()
            CacheManager.set_cached_data(key, fresh_data, ttl_seconds)
            return fresh_data, False
        except Exception as e:
            # Fetch failed - try to get stale data
            stale_data = CacheManager.get_stale_data(key)
            if stale_data is not None:
                return stale_data, True
            raise e
    
    @staticmethod
    def clear_all() -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries removed.
        """
        return CacheManager.invalidate_cache("*")
    
    @staticmethod
    def get_cache_stats() -> dict:
        """
        Get statistics about the current cache state.
        
        Returns:
            Dictionary with cache statistics.
        """
        # Get MongoDB stats
        mongo_stats = MongoCacheManager.get_cache_stats()
        
        # Get session_state stats
        state = CacheManager._get_session_state()
        
        session_total = 0
        session_valid = 0
        session_expired = 0
        
        now = datetime.now()
        
        for key in state.keys():
            if key.startswith(CACHE_PREFIX):
                session_total += 1
                entry: CacheEntry = state[key]
                if now < entry.expires_at:
                    session_valid += 1
                else:
                    session_expired += 1
        
        return {
            "mongodb_enabled": mongo_stats.get("enabled", False),
            "mongodb_entries": mongo_stats.get("valid_entries", 0),
            "session_entries": session_valid,
            "total_entries": mongo_stats.get("valid_entries", 0) + session_valid,
            "valid_entries": mongo_stats.get("valid_entries", 0) + session_valid,
            "expired_entries": mongo_stats.get("expired_entries", 0) + session_expired
        }

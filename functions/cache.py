"""
Caching mechanism for search_ontologies endpoint.

This module provides a flexible caching system that:
- Uses in-memory caching by default (TTLCache from cachetools)
- Can be upgraded to Redis for distributed caching
- Handles cache key generation based on search parameters and user context
- Provides cache invalidation helpers
"""
import os
import hashlib
import json
from typing import Optional, Any, Dict
from functools import wraps
from datetime import datetime
import logging

try:
    from cachetools import TTLCache
    CACHE_TOOLS_AVAILABLE = True
except ImportError:
    CACHE_TOOLS_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cache configuration from environment variables
CACHE_TTL = int(os.getenv('CACHE_TTL_SECONDS', 300))  # Default: 5 minutes
CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', 128))  # Default: 128 entries
USE_REDIS = os.getenv('USE_REDIS_CACHE', 'false').lower() == 'true'
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'

# Initialize cache
_cache: Optional[Any] = None
_redis_client: Optional[Any] = None


def _get_cache():
    """Get or initialize the cache instance."""
    global _cache, _redis_client
    
    if not CACHE_ENABLED:
        return None
    
    if USE_REDIS and REDIS_AVAILABLE:
        if _redis_client is None:
            try:
                _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                # Test connection
                _redis_client.ping()
                logger.info(f"Redis cache initialized with URL: {REDIS_URL}")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}. Falling back to in-memory cache.")
                _redis_client = None
        return _redis_client
    elif CACHE_TOOLS_AVAILABLE:
        if _cache is None:
            _cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)
            logger.info(f"In-memory cache initialized with TTL={CACHE_TTL}s, maxsize={CACHE_MAX_SIZE}")
        return _cache
    else:
        logger.warning("No caching library available. Install cachetools for in-memory caching.")
        return None


def _generate_cache_key(search_term: Optional[str], limit: int, offset: int, fuid: Optional[str]) -> str:
    """
    Generate a cache key based on search parameters and user context.
    
    Args:
        search_term: Search term (normalized to lowercase, None if empty)
        limit: Maximum number of results
        offset: Pagination offset
        fuid: Firebase UID for user context (affects which ontologies are visible)
        
    Returns:
        A unique cache key string
    """
    # Normalize search_term (empty string becomes None, lowercase for consistency)
    normalized_search = None
    if search_term:
        normalized_search = search_term.strip().lower()
        if not normalized_search:
            normalized_search = None
    
    # Create a dictionary of cache parameters
    cache_params = {
        'search_term': normalized_search,
        'limit': limit,
        'offset': offset,
        'fuid': fuid  # Include user context for permission-based filtering
    }
    
    # Convert to JSON string for consistent hashing
    params_json = json.dumps(cache_params, sort_keys=True)
    
    # Generate hash for shorter key
    key_hash = hashlib.sha256(params_json.encode()).hexdigest()
    
    # Return a human-readable prefix + hash
    return f"search_ontologies:{key_hash}"


def get_cached_result(search_term: Optional[str], limit: int, offset: int, fuid: Optional[str]) -> Optional[Any]:
    """
    Retrieve a cached result for search_ontologies query.
    
    Args:
        search_term: Search term
        limit: Maximum number of results
        offset: Pagination offset
        fuid: Firebase UID
        
    Returns:
        Cached result if available, None otherwise
    """
    cache = _get_cache()
    if cache is None:
        return None
    
    cache_key = _generate_cache_key(search_term, limit, offset, fuid)
    
    try:
        if USE_REDIS and isinstance(cache, redis.Redis):
            cached_data = cache.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        else:
            # In-memory cache (TTLCache)
            return cache.get(cache_key)
    except Exception as e:
        logger.error(f"Error retrieving from cache: {e}")
        return None


def set_cached_result(search_term: Optional[str], limit: int, offset: int, fuid: Optional[str], result: Any) -> None:
    """
    Store a result in the cache.
    
    Args:
        search_term: Search term
        limit: Maximum number of results
        offset: Pagination offset
        fuid: Firebase UID
        result: The result to cache (should be serializable)
    """
    cache = _get_cache()
    if cache is None:
        return
    
    cache_key = _generate_cache_key(search_term, limit, offset, fuid)
    
    try:
        if USE_REDIS and isinstance(cache, redis.Redis):
            # Redis requires JSON serialization
            cache.setex(
                cache_key,
                CACHE_TTL,
                json.dumps(result, default=str)  # default=str handles datetime serialization
            )
        else:
            # In-memory cache (TTLCache)
            cache[cache_key] = result
    except Exception as e:
        logger.error(f"Error storing in cache: {e}")


def invalidate_search_cache() -> None:
    """
    Invalidate all search cache entries.
    
    This is called when ontologies are added, updated, or deleted.
    """
    cache = _get_cache()
    if cache is None:
        return
    
    try:
        if USE_REDIS and isinstance(cache, redis.Redis):
            # Find all keys matching the pattern
            pattern = "search_ontologies:*"
            keys = cache.keys(pattern)
            if keys:
                cache.delete(*keys)
                logger.info(f"Invalidated {len(keys)} Redis cache entries")
        else:
            # For in-memory cache, we need to clear all entries
            # TTLCache doesn't support pattern matching, so we clear everything
            cache.clear()
            logger.info("Cleared in-memory search cache")
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")


def cache_search_results(func):
    """
    Decorator to cache search_ontologies function results.
    
    This decorator wraps the search function to:
    1. Check cache before executing the query
    2. Store results in cache after execution
    3. Handle cache errors gracefully
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract parameters for cache key generation
        # Handle both positional and keyword arguments
        search_term = kwargs.get('search_term', None)
        limit = kwargs.get('limit', 100)
        offset = kwargs.get('offset', 0)
        request = kwargs.get('request', None)
        
        # Fallback to positional args if not in kwargs
        if search_term is None and len(args) > 0:
            search_term = args[0]
        if 'limit' not in kwargs and len(args) > 1:
            limit = args[1]
        if 'offset' not in kwargs and len(args) > 2:
            offset = args[2]
        if request is None and len(args) > 3:
            request = args[3]
        
        # Normalize search_term
        if search_term is not None:
            search_term = search_term.strip() if isinstance(search_term, str) else None
            if search_term == '':
                search_term = None
        
        # Extract fuid from request if available
        fuid = None
        if request is not None:
            try:
                auth_header = None
                if hasattr(request, 'headers'):
                    if isinstance(request.headers, dict):
                        auth_header = request.headers.get('Authorization')
                    elif hasattr(request.headers, 'get'):
                        auth_header = request.headers.get('Authorization')
                
                if auth_header:
                    from .auth_utils import verify_firebase_token
                    parts = auth_header.split()
                    if len(parts) == 2 and parts[0].lower() == 'bearer':
                        decoded = verify_firebase_token(parts[1])
                        fuid = decoded.get('uid')
            except Exception as e:
                logger.debug(f"Could not extract fuid from request: {e}")
                fuid = None
        
        # Try to get from cache
        if CACHE_ENABLED:
            cached_result = get_cached_result(search_term, limit, offset, fuid)
            if cached_result is not None:
                logger.info(f"Cache hit for search: term='{search_term}', limit={limit}, offset={offset}, fuid={fuid[:8] + '...' if fuid else 'None'}")
                # Convert dict back to OntologyResponse if needed
                from .model_ontology import OntologyResponse
                if isinstance(cached_result, dict):
                    return OntologyResponse(**cached_result)
                return cached_result
        
        # Cache miss - execute the function
        logger.debug(f"Cache miss for search: term='{search_term}', limit={limit}, offset={offset}")
        result = func(*args, **kwargs)
        
        # Store in cache (convert OntologyResponse to dict for serialization)
        if CACHE_ENABLED and result is not None:
            try:
                if hasattr(result, 'model_dump'):
                    cache_data = result.model_dump()
                elif hasattr(result, 'dict'):
                    cache_data = result.dict()
                else:
                    cache_data = result
                set_cached_result(search_term, limit, offset, fuid, cache_data)
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")
        
        return result
    
    return wrapper


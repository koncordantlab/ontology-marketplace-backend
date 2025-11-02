# Caching Mechanism for `/search_ontologies` Endpoint

This document describes the caching mechanism implemented for the `/search_ontologies` endpoint to improve performance and reduce database load.

## Overview

The caching system provides:
- **In-memory caching** by default (using `cachetools.TTLCache`)
- **Optional Redis support** for distributed caching
- **Automatic cache invalidation** when ontologies are added, updated, or deleted
- **User-aware caching** that respects authentication and permissions

## Architecture

### Cache Key Generation

Cache keys are generated based on:
- `search_term`: Normalized search query (lowercase, trimmed, None if empty)
- `limit`: Maximum number of results (pagination)
- `offset`: Pagination offset
- `fuid`: Firebase UID of the authenticated user (for permission-based filtering)

This ensures that:
- Different users see cached results based on their permissions
- Search queries are cached separately from paginated results
- Empty/null search terms are normalized to prevent duplicate cache entries

### Cache Implementation

The system supports two caching backends:

#### 1. In-Memory Cache (Default)
- Uses `cachetools.TTLCache` for automatic expiration
- Fast and zero-configuration
- Cache is lost on application restart
- Suitable for single-instance deployments

#### 2. Redis Cache (Optional)
- Distributed caching across multiple instances
- Persistent across application restarts
- Better for production deployments with multiple instances
- Requires Redis server to be available

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_ENABLED` | `true` | Enable/disable caching entirely |
| `CACHE_TTL_SECONDS` | `300` | Time-to-live for cache entries (5 minutes) |
| `CACHE_MAX_SIZE` | `128` | Maximum number of entries in in-memory cache |
| `USE_REDIS_CACHE` | `false` | Use Redis instead of in-memory cache |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (only if `USE_REDIS_CACHE=true`) |

### Example Configuration

#### In-Memory Cache (Default)
```bash
# Use defaults - no configuration needed
# Or customize TTL and size:
export CACHE_TTL_SECONDS=600  # 10 minutes
export CACHE_MAX_SIZE=256
```

#### Redis Cache
```bash
export USE_REDIS_CACHE=true
export REDIS_URL=redis://your-redis-host:6379/0
export CACHE_TTL_SECONDS=300
```

#### Disable Caching
```bash
export CACHE_ENABLED=false
```

## Cache Invalidation

The cache is automatically invalidated when:
1. **Ontologies are added** (`/add_ontologies` endpoint)
2. **Ontologies are updated** (`/update_ontology/{ontology_uuid}` endpoint)
3. **Ontologies are deleted** (`/delete_ontologies` endpoint)

This ensures that cached results are always fresh and reflect the current state of the database.

## Usage

### For Developers

The caching is transparent - no code changes needed in your endpoints. The `@cache_search_results` decorator is applied to the `search_ontologies` function.

```python
from .cache import cache_search_results

@cache_search_results
def search_ontologies(...):
    # Your existing implementation
    ...
```

### Manual Cache Invalidation

If you need to manually invalidate the cache (e.g., after bulk operations):

```python
from .cache import invalidate_search_cache

invalidate_search_cache()
```

## Performance Considerations

### Cache Hit Scenarios
- Repeated searches with the same parameters
- Pagination through results (each page is cached separately)
- Popular search queries

### Cache Miss Scenarios
- First-time searches
- Searches after cache expiration (TTL)
- Searches after cache invalidation (add/update/delete operations)
- Different users searching (different cache keys due to fuid)

### Expected Performance Improvements
- **Cache Hit**: ~1-5ms (memory lookup) vs ~50-200ms (Neo4j query)
- **Redis Cache Hit**: ~10-20ms (network round-trip) vs ~50-200ms (Neo4j query)
- **Reduced Database Load**: Significant reduction in Neo4j queries for popular searches

## Monitoring

The cache module logs the following events:
- Cache initialization (backend type, TTL, size)
- Cache hits (with search parameters)
- Cache misses (for debugging)
- Cache invalidation (number of entries cleared)
- Errors (failures to read/write cache)

Look for log messages prefixed with cache-related information.

## Troubleshooting

### Cache Not Working
1. Check `CACHE_ENABLED=true` is set
2. Verify cachetools is installed: `pip install cachetools`
3. Check application logs for cache initialization messages
4. For Redis: verify connection and that Redis is running

### Stale Cache Data
1. Verify cache invalidation is called after mutations
2. Check TTL is appropriate for your use case
3. Consider reducing `CACHE_TTL_SECONDS` if data changes frequently

### Redis Connection Issues
1. Verify Redis is running: `redis-cli ping`
2. Check `REDIS_URL` is correct
3. Verify network connectivity to Redis server
4. Check Redis authentication if required

## Upgrading to Redis

To upgrade from in-memory to Redis caching:

1. **Install Redis** (if not already available):
   ```bash
   # Local development
   brew install redis  # macOS
   sudo apt-get install redis-server  # Linux
   
   # Or use Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

2. **Install Redis Python client**:
   ```bash
   pip install redis
   ```
   Add to `pyproject.toml`:
   ```toml
   dependencies = [
       ...
       "redis>=5.0.0",
   ]
   ```

3. **Set environment variables**:
   ```bash
   export USE_REDIS_CACHE=true
   export REDIS_URL=redis://localhost:6379/0
   ```

4. **Restart your application**

## Best Practices

1. **TTL Selection**: 
   - Short TTL (1-5 minutes) for frequently changing data
   - Longer TTL (10-30 minutes) for relatively static data
   - Balance freshness vs. performance

2. **Cache Size**:
   - In-memory: Start with 128, increase if you have memory available
   - Redis: Typically no size limit needed (handled by Redis)

3. **Monitoring**:
   - Monitor cache hit rates
   - Track cache invalidation frequency
   - Watch for cache-related errors in logs

4. **Production Deployment**:
   - Use Redis for multi-instance deployments
   - Set up Redis monitoring and persistence
   - Consider Redis replication for high availability

## Implementation Details

### File Structure
- `functions/cache.py`: Core caching logic and decorators
- `functions/search_ontologies.py`: Uses `@cache_search_results` decorator
- `functions/add_ontologies.py`: Calls `invalidate_search_cache()`
- `functions/update_ontology.py`: Calls `invalidate_search_cache()`
- `functions/delete_ontologies.py`: Calls `invalidate_search_cache()`

### Cache Key Format
```
search_ontologies:{sha256_hash_of_parameters}
```

The hash is generated from a JSON-serialized dictionary of:
```json
{
  "search_term": "normalized search term or null",
  "limit": 100,
  "offset": 0,
  "fuid": "firebase_uid or null"
}
```

This ensures consistent cache keys across requests with the same parameters.


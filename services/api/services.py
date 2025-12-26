"""
Business logic service layer
"""
import logging
from typing import List, Optional
from repositories import MovieRepository
from cache import CacheService
from shared import Movie, MovieSearchQuery, MovieResponse

logger = logging.getLogger(__name__)


class MovieService:
    """Movie business logic service"""
    
    def __init__(self, repository: MovieRepository, cache: CacheService):
        self.repository = repository
        self.cache = cache
    
    async def get_movie_by_id(self, movie_id: str) -> Optional[Movie]:
        """Get movie by ID with caching"""
        # Try cache first
        cache_key = self.cache.cache_key("movie", movie_id)
        cached_movie = await self.cache.get(cache_key)
        
        if cached_movie:
            logger.debug(f"Cache hit for movie {movie_id}")
            return Movie(**cached_movie)
        
        # Fetch from database
        movie = await self.repository.get_movie_by_id(movie_id)
        
        if movie:
            # Cache the result
            await self.cache.set(cache_key, movie.dict())
            logger.debug(f"Cached movie {movie_id}")
        
        return movie
    
    async def search_movies(self, query: MovieSearchQuery) -> MovieResponse:
        """Search movies with caching"""
        # Generate cache key from query parameters
        cache_key = self.cache.cache_key(
            "search",
            query.title or "",
            query.year or "",
            "|".join(query.genre) if query.genre else "",
            query.cast or "",
            query.director or "",
            query.rating or "",
            query.limit,
            query.offset
        )
        
        # Try cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.debug("Cache hit for search query")
            return MovieResponse(**cached_result)
        
        # Build filters for repository
        filters = {}
        if query.title:
            filters["title"] = query.title
        if query.year:
            filters["year"] = query.year
        if query.genre:
            filters["genre"] = query.genre
        if query.cast:
            filters["cast"] = query.cast
        if query.director:
            filters["director"] = query.director
        if query.rating:
            filters["rating"] = query.rating
        
        # Search in database
        movies, total = await self.repository.search_movies(filters, query.limit, query.offset)
        
        response = MovieResponse(
            data=movies,
            pagination={
                "limit": query.limit,
                "offset": query.offset,
                "total": total
            },
            total=total
        )
        
        # Cache the result (shorter TTL for search results)
        await self.cache.set(cache_key, response.dict(), ttl=300)  # 5 minutes
        
        return response
    
    # Full-text search removed - all queries handled via search_movies with PostgreSQL
    
    async def create_movie(self, movie: Movie) -> Optional[Movie]:
        """Create a new movie"""
        # Create in database
        created_movie = await self.repository.create_movie(movie)
        
        if created_movie:
            # Cache the movie
            cache_key = self.cache.cache_key("movie", created_movie.id)
            await self.cache.set(cache_key, created_movie.dict())
            
            # Invalidate search cache
            await self.cache.invalidate_pattern("search:*")
            
            logger.info(f"Created movie: {created_movie.title} ({created_movie.id})")
        
        return created_movie
    
    async def update_movie(self, movie: Movie) -> Optional[Movie]:
        """Update an existing movie"""
        # Update in database
        updated_movie = await self.repository.update_movie(movie)
        
        if updated_movie:
            # Invalidate cache
            cache_key = self.cache.cache_key("movie", updated_movie.id)
            await self.cache.delete(cache_key)
            await self.cache.invalidate_pattern("search:*")
            
            logger.info(f"Updated movie: {updated_movie.title} ({updated_movie.id})")
        
        return updated_movie
    
    async def delete_movie(self, movie_id: str) -> bool:
        """Delete a movie"""
        # Delete from database
        deleted = await self.repository.delete_movie(movie_id)
        
        if deleted:
            # Invalidate cache
            cache_key = self.cache.cache_key("movie", movie_id)
            await self.cache.delete(cache_key)
            await self.cache.invalidate_pattern("search:*")
            
            logger.info(f"Deleted movie: {movie_id}")
        
        return deleted
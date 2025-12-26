"""
FastAPI Movie Store API Service
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from shared.database import Database
from cache import CacheService
from shared.repositories import MovieRepository
from services import MovieService

# Import shared models
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared import Movie, MovieSearchQuery, MovieResponse, HealthCheck, config


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.app.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 Starting Movie Store API...")
    
    # Initialize services
    await app.state.database.connect()
    await app.state.cache.connect()
    
    logger.info("✅ All services connected successfully")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Movie Store API...")
    await app.state.database.disconnect()
    await app.state.cache.disconnect()
    logger.info("✅ Graceful shutdown completed")


# Create FastAPI app
app = FastAPI(
    title="Movie Store API",
    description="RESTful API for querying movie data from multiple providers",
    version=config.app.version,
    lifespan=lifespan,
    docs_url="/docs" if config.app.debug else None,
    redoc_url="/redoc" if config.app.debug else None
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.app.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Initialize services
app.state.database = Database(config.database)
app.state.cache = CacheService(config.redis)


def get_movie_service() -> MovieService:
    """Dependency injection for movie service"""
    movie_repo = MovieRepository(app.state.database)
    return MovieService(
        repository=movie_repo,
        cache=app.state.cache
    )


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Movie Store API",
        "version": config.app.version,
        "docs_url": "/docs" if config.app.debug else "Contact admin for API documentation"
    }


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    services = {}
    
    try:
        # Check database
        db_status = await app.state.database.health_check()
        services["database"] = "healthy" if db_status else "unhealthy"
    except Exception as e:
        services["database"] = f"error: {str(e)}"
    
    try:
        # Check cache
        cache_status = await app.state.cache.health_check()
        services["cache"] = "healthy" if cache_status else "unhealthy"
    except Exception as e:
        services["cache"] = f"error: {str(e)}"
    
    # Elasticsearch removed - using PostgreSQL for all queries
    services["search"] = "postgresql-based"
    
    # Overall status
    status = "healthy" if all("healthy" in s for s in services.values()) else "degraded"
    
    return HealthCheck(
        status=status,
        timestamp=datetime.utcnow(),
        version=config.app.version,
        services=services
    )


@app.get("/api/v1/movies", response_model=MovieResponse)
async def list_movies(
    title: str = Query(None, description="Filter by movie title"),
    year: int = Query(None, ge=1888, le=2030, description="Filter by release year"),
    genre: List[str] = Query(default=[], description="Filter by genre(s)"),
    cast: str = Query(None, description="Filter by cast member name"),
    director: str = Query(None, description="Filter by director name"),
    rating: str = Query(None, description="Filter by MPAA rating"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    movie_service: MovieService = Depends(get_movie_service)
):
    """
    List movies with optional filters
    
    Supports filtering by:
    - title: Partial text search in movie titles
    - year: Exact year match
    - genre: One or more genres (OR logic)
    - cast: Partial name search in cast members
    - director: Partial name search in directors
    - rating: MPAA rating (G, PG, PG-13, R, NC-17, NR)
    """
    try:
        query = MovieSearchQuery(
            title=title,
            year=year,
            genre=genre,
            cast=cast,
            director=director,
            rating=rating,
            limit=limit,
            offset=offset
        )
        
        result = await movie_service.search_movies(query)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching movies: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/movies/{movie_id}", response_model=Movie)
async def get_movie(
    movie_id: str,
    movie_service: MovieService = Depends(get_movie_service)
):
    """Get a specific movie by ID"""
    try:
        movie = await movie_service.get_movie_by_id(movie_id)
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        return movie
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching movie {movie_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Full-text search removed - all queries handled via /api/v1/movies with filters


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.app.host,
        port=config.app.port,
        log_level=config.app.log_level.lower(),
        reload=config.app.debug
    )

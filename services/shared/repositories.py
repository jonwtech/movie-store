"""
Data repository layer
"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from shared.database import MovieModel, Database
from shared import Movie

logger = logging.getLogger(__name__)


class MovieRepository:
    """Movie data repository"""
    
    def __init__(self, database: Database):
        self.database = database
    
    async def create_movie(self, movie: Movie) -> Optional[Movie]:
        """Create a new movie"""
        try:
            async with self.database.get_session() as session:
                movie_data = movie.dict(exclude={'created_at', 'updated_at'})
                db_movie = MovieModel(**movie_data)
                
                session.add(db_movie)
                await session.commit()
                await session.refresh(db_movie)
                
                return self._model_to_movie(db_movie)
                
        except Exception as e:
            logger.error(f"Error creating movie: {str(e)}")
            return None
    
    async def get_movie_by_id(self, movie_id: str) -> Optional[Movie]:
        """Get movie by ID"""
        try:
            async with self.database.get_session() as session:
                stmt = select(MovieModel).where(MovieModel.id == movie_id)
                result = await session.execute(stmt)
                db_movie = result.scalar_one_or_none()
                
                return self._model_to_movie(db_movie) if db_movie else None
                
        except Exception as e:
            logger.error(f"Error fetching movie {movie_id}: {str(e)}")
            return None
    
    async def update_movie(self, movie: Movie) -> Optional[Movie]:
        """Update an existing movie"""
        try:
            async with self.database.get_session() as session:
                stmt = select(MovieModel).where(MovieModel.id == movie.id)
                result = await session.execute(stmt)
                db_movie = result.scalar_one_or_none()
                
                if not db_movie:
                    return None
                
                # Update fields
                movie_data = movie.dict(exclude={'id', 'created_at', 'updated_at'})
                for key, value in movie_data.items():
                    if hasattr(db_movie, key):
                        setattr(db_movie, key, value)
                
                await session.commit()
                await session.refresh(db_movie)
                
                return self._model_to_movie(db_movie)
                
        except Exception as e:
            logger.error(f"Error updating movie {movie.id}: {str(e)}")
            return None
    
    async def delete_movie(self, movie_id: str) -> bool:
        """Delete a movie"""
        try:
            async with self.database.get_session() as session:
                stmt = select(MovieModel).where(MovieModel.id == movie_id)
                result = await session.execute(stmt)
                db_movie = result.scalar_one_or_none()
                
                if not db_movie:
                    return False
                
                await session.delete(db_movie)
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error deleting movie {movie_id}: {str(e)}")
            return False
    
    async def search_movies(self, filters: Dict[str, Any], limit: int = 20, offset: int = 0) -> tuple[List[Movie], int]:
        """Search movies with filters"""
        try:
            async with self.database.get_session() as session:
                # Build query
                stmt = select(MovieModel)
                count_stmt = select(func.count(MovieModel.id))
                
                conditions = []
                
                # Apply filters
                if filters.get("title"):
                    conditions.append(MovieModel.title.ilike(f"%{filters['title']}%"))
                
                if filters.get("year"):
                    conditions.append(MovieModel.year == filters["year"])
                
                if filters.get("genre"):
                    # PostgreSQL array overlap operator
                    genres = filters["genre"] if isinstance(filters["genre"], list) else [filters["genre"]]
                    conditions.append(MovieModel.genre.overlap(genres))
                
                if filters.get("director"):
                    conditions.append(MovieModel.director.ilike(f"%{filters['director']}%"))
                
                if filters.get("rating"):
                    conditions.append(MovieModel.rating == filters["rating"])
                
                if filters.get("cast"):
                    # Search in cast JSON field
                    cast_query = f"%{filters['cast']}%"
                    conditions.append(MovieModel.cast.astext.ilike(cast_query))
                
                # Apply conditions
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                    count_stmt = count_stmt.where(and_(*conditions))
                
                # Get total count
                count_result = await session.execute(count_stmt)
                total = count_result.scalar() or 0
                
                # Apply pagination and ordering
                stmt = stmt.order_by(MovieModel.year.desc(), MovieModel.title)
                stmt = stmt.offset(offset).limit(limit)
                
                # Execute query
                result = await session.execute(stmt)
                db_movies = result.scalars().all()
                
                movies = [self._model_to_movie(db_movie) for db_movie in db_movies]
                return movies, total
                
        except Exception as e:
            logger.error(f"Error searching movies: {str(e)}")
            return [], 0
    
    async def get_movies_by_ids(self, movie_ids: List[str]) -> List[Movie]:
        """Get multiple movies by IDs"""
        try:
            async with self.database.get_session() as session:
                stmt = select(MovieModel).where(MovieModel.id.in_(movie_ids))
                result = await session.execute(stmt)
                db_movies = result.scalars().all()
                
                return [self._model_to_movie(db_movie) for db_movie in db_movies]
                
        except Exception as e:
            logger.error(f"Error fetching movies by IDs: {str(e)}")
            return []
    
    def _model_to_movie(self, db_movie: MovieModel) -> Movie:
        """Convert database model to Movie object"""
        return Movie(
            id=db_movie.id,
            title=db_movie.title,
            year=db_movie.year,
            genre=db_movie.genre,
            cast=db_movie.cast or [],
            director=db_movie.director,
            runtime_minutes=db_movie.runtime_minutes,
            rating=db_movie.rating,
            imdb_id=db_movie.imdb_id,
            budget_usd=db_movie.budget_usd,
            box_office_usd=db_movie.box_office_usd,
            synopsis=db_movie.synopsis,
            poster_url=db_movie.poster_url,
            trailer_url=db_movie.trailer_url,
            provider_metadata=db_movie.provider_metadata or {},
            created_at=db_movie.created_at,
            updated_at=db_movie.updated_at
        )

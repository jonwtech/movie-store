"""
Database connection and management
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

Base = declarative_base()


class MovieModel(Base):
    """SQLAlchemy model for movies"""
    __tablename__ = "movies"

    id = Column(String(100), primary_key=True)
    title = Column(String(500), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    genre = Column(ARRAY(String), nullable=False, index=True)
    cast = Column(JSON, default=list)
    director = Column(String(200), index=True)
    runtime_minutes = Column(Integer)
    rating = Column(String(10))
    imdb_id = Column(String(20), unique=True, index=True)
    budget_usd = Column(Integer)
    box_office_usd = Column(Integer)
    synopsis = Column(Text)
    poster_url = Column(String(500))
    trailer_url = Column(String(500))
    provider_metadata = Column(JSON, default=dict)
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Movie(id='{self.id}', title='{self.title}', year={self.year})>"


class Database:
    """Database connection manager"""
    
    def __init__(self, config):
        self.config = config
        self.engine = None
        self.session_factory = None
    
    async def connect(self):
        """Initialize database connection"""
        try:
            self.engine = create_async_engine(
                self.config.url,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                echo=False  # Set to True for SQL debugging
            )
            
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables if they don't exist
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✅ Database connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Database connection failed: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database disconnected")
    
    async def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.session_factory:
            raise RuntimeError("Database not connected")
        return self.session_factory()
    
    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.get_session() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False
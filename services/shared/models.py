"""
Shared data models for the movie store platform
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class Genre(str, Enum):
    """Movie genres enum"""
    ACTION = "Action"
    ADVENTURE = "Adventure"
    ANIMATION = "Animation"
    BIOGRAPHY = "Biography"
    COMEDY = "Comedy"
    CRIME = "Crime"
    DOCUMENTARY = "Documentary"
    DRAMA = "Drama"
    FAMILY = "Family"
    FANTASY = "Fantasy"
    HISTORY = "History"
    HORROR = "Horror"
    MUSIC = "Music"
    MUSICAL = "Musical"
    MYSTERY = "Mystery"
    ROMANCE = "Romance"
    SCI_FI = "Sci-Fi"
    SPORT = "Sport"
    THRILLER = "Thriller"
    WAR = "War"
    WESTERN = "Western"


class Rating(str, Enum):
    """MPAA ratings enum"""
    G = "G"
    PG = "PG"
    PG_13 = "PG-13"
    R = "R"
    NC_17 = "NC-17"
    NR = "NR"


class CastMember(BaseModel):
    """Cast member model"""
    name: str = Field(..., min_length=1, max_length=200)
    role: str = Field(..., min_length=1, max_length=200)
    character: Optional[str] = Field(None, max_length=200)


class Movie(BaseModel):
    """Movie data model"""
    id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    year: int = Field(..., ge=1888, le=2030)
    genre: List[Genre] = Field(..., min_items=1, max_items=5)
    cast: Optional[List[CastMember]] = Field(default=[], max_items=100)
    director: Optional[str] = Field(None, max_length=200)
    runtime_minutes: Optional[int] = Field(None, ge=1, le=600)
    rating: Optional[Rating] = None
    imdb_id: Optional[str] = Field(None, pattern=r"^tt\d{7,8}$")
    budget_usd: Optional[int] = Field(None, ge=0, le=1_000_000_000)
    box_office_usd: Optional[int] = Field(None, ge=0, le=10_000_000_000)
    synopsis: Optional[str] = Field(None, max_length=2000)
    poster_url: Optional[str] = Field(None, max_length=500)
    trailer_url: Optional[str] = Field(None, max_length=500)
    provider_metadata: Optional[Dict[str, Any]] = Field(default=None, default_factory=dict)
    
    # System fields
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @validator('genre')
    def unique_genres(cls, v):
        """Ensure genres are unique"""
        if len(v) != len(set(v)):
            raise ValueError('Genres must be unique')
        return v

    @validator('cast')
    def unique_cast_names(cls, v):
        """Ensure cast member names are unique"""
        if v:
            names = [member.name.lower() for member in v]
            if len(names) != len(set(names)):
                raise ValueError('Cast member names must be unique')
        return v

    class Config:
        use_enum_values = True


class MovieSearchQuery(BaseModel):
    """Movie search query parameters"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    year: Optional[int] = Field(None, ge=1888, le=2030)
    genre: Optional[List[Genre]] = Field(default=[])
    cast: Optional[str] = Field(None, min_length=1, max_length=200)
    director: Optional[str] = Field(None, min_length=1, max_length=200)
    rating: Optional[Rating] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

    class Config:
        use_enum_values = True


class MovieResponse(BaseModel):
    """API response for movie data"""
    data: List[Movie]
    pagination: Dict[str, int]
    total: int


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]

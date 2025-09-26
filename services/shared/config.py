"""
Shared configuration for movie store services
"""
import os
from typing import Optional
from pydantic import BaseSettings, Field


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    host: str = Field(..., env="DB_HOST")
    port: int = Field(5432, env="DB_PORT")
    name: str = Field(..., env="DB_NAME")
    user: str = Field(..., env="DB_USER")
    password: str = Field(..., env="DB_PASSWORD")
    pool_size: int = Field(10, env="DB_POOL_SIZE")
    max_overflow: int = Field(20, env="DB_MAX_OVERFLOW")

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    class Config:
        env_prefix = "DB_"


class RedisConfig(BaseSettings):
    """Redis configuration"""
    host: str = Field(..., env="REDIS_HOST")
    port: int = Field(6379, env="REDIS_PORT")
    db: int = Field(0, env="REDIS_DB")
    password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    ttl_seconds: int = Field(3600, env="REDIS_TTL")  # 1 hour default

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    class Config:
        env_prefix = "REDIS_"


class AWSConfig(BaseSettings):
    """AWS configuration"""
    region: str = Field("eu-west-1", env="AWS_REGION")
    sqs_queue_url: str = Field(..., env="SQS_QUEUE_URL")
    s3_bucket: str = Field(..., env="S3_BUCKET")
    
    class Config:
        env_prefix = "AWS_"


class AppConfig(BaseSettings):
    """Application configuration"""
    name: str = Field("movie-store-api", env="APP_NAME")
    version: str = Field("1.0.0", env="APP_VERSION")
    environment: str = Field("dev", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    debug: bool = Field(False, env="DEBUG")
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    
    # Security
    cors_origins: list = Field(["*"], env="CORS_ORIGINS")
    rate_limit_per_minute: int = Field(100, env="RATE_LIMIT_PER_MINUTE")
    
    class Config:
        env_prefix = "APP_"


class Config:
    """Main configuration class"""
    
    def __init__(self):
        self.app = AppConfig()
        self.database = DatabaseConfig()
        self.redis = RedisConfig()
        self.aws = AWSConfig()
    
    @property
    def is_production(self) -> bool:
        return self.app.environment == "prod"
    
    @property
    def is_development(self) -> bool:
        return self.app.environment == "dev"


# Global config instance
config = Config()

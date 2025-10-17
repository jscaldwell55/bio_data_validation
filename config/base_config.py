# config/base_config.py
"""
Application configuration with environment variable support.
Uses pydantic-settings for type-safe configuration management.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    Application configuration with environment variable support.
    
    All settings can be overridden via environment variables or .env file.
    """
    
    # =============================================================================
    # Application Settings
    # =============================================================================
    APP_NAME: str = "Bio-Data-Validation"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False
    
    # =============================================================================
    # Database Settings
    # =============================================================================
    DATABASE_URL: str = "sqlite:///./bio_validation.db"
    
    # =============================================================================
    # External API Settings
    # =============================================================================
    # NCBI E-utilities
    NCBI_API_KEY: Optional[str] = None
    NCBI_BASE_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    NCBI_BATCH_SIZE: int = 50
    NCBI_RATE_LIMIT_DELAY: float = 0.34  # Default (no API key)
    NCBI_MAX_RETRIES: int = 3
    NCBI_TIMEOUT: int = 30  # seconds
    
    # Ensembl REST API
    ENSEMBL_API_URL: str = "https://rest.ensembl.org"
    ENSEMBL_BATCH_SIZE: int = 50
    ENSEMBL_RATE_LIMIT_DELAY: float = 0.067  # 15 req/sec
    ENSEMBL_TIMEOUT: int = 30  # seconds
    ENSEMBL_ENABLED: bool = True  # 🆕 Enable Ensembl fallback
    
    # =============================================================================
    # 🆕 Caching Settings
    # =============================================================================
    CACHE_ENABLED: bool = True  # Enable gene symbol caching
    CACHE_PATH: str = "validation_cache.db"  # SQLite cache file
    CACHE_TTL_HOURS: int = 168  # 7 days (genes rarely change)
    CACHE_AUTO_WARM: bool = True  # Pre-populate common genes
    
    # =============================================================================
    # MLOps Settings
    # =============================================================================
    MLFLOW_TRACKING_URI: str = "sqlite:///./mlruns.db"
    MLFLOW_EXPERIMENT_NAME: str = "bio-validation"
    MLFLOW_ENABLE_TRACKING: bool = False
    
    # Data Version Control (DVC)
    DVC_REMOTE_URL: Optional[str] = None
    DVC_CACHE_DIR: str = ".dvc/cache"
    
    # =============================================================================
    # Monitoring & Observability
    # =============================================================================
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None
    
    # Prometheus metrics
    PROMETHEUS_ENABLED: bool = False
    PROMETHEUS_PORT: int = 9090
    PROMETHEUS_PATH: str = "/metrics"
    
    # =============================================================================
    # Validation Orchestrator Settings
    # =============================================================================
    ORCHESTRATOR_TIMEOUT_SECONDS: int = 300
    ENABLE_SHORT_CIRCUIT: bool = True
    ENABLE_PARALLEL_BIO: bool = True
    
    # =============================================================================
    # Policy & Rules Configuration
    # =============================================================================
    POLICY_CONFIG_PATH: str = "config/policy_config.yml"
    VALIDATION_RULES_PATH: str = "config/validation_rules.yml"
    
    # =============================================================================
    # API Server Settings
    # =============================================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_RELOAD: bool = False
    
    # CORS settings
    CORS_ENABLED: bool = True
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # =============================================================================
    # Performance & Resource Limits
    # =============================================================================
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_RECORDS_PER_VALIDATION: int = 100000
    WORKER_POOL_SIZE: int = 4
    
    # =============================================================================
    # Security Settings
    # =============================================================================
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY_ENABLED: bool = False
    API_KEY_HEADER: str = "X-API-Key"
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"
    
    def __init__(self, **kwargs):
        """Initialize settings with dynamic rate limit adjustment"""
        super().__init__(**kwargs)
        
        # Dynamically adjust NCBI rate limit based on API key
        if self.NCBI_API_KEY:
            self.NCBI_RATE_LIMIT_DELAY = 0.1  # 10 req/sec with key
        else:
            self.NCBI_RATE_LIMIT_DELAY = 0.34  # 3 req/sec without key
    
    @property
    def ncbi_requests_per_second(self) -> int:
        """Calculate NCBI requests per second"""
        return int(1.0 / self.NCBI_RATE_LIMIT_DELAY)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT.lower() == "development"
    
    def get_database_path(self) -> Optional[Path]:
        """Get database path if using SQLite"""
        if self.DATABASE_URL.startswith("sqlite:///"):
            return Path(self.DATABASE_URL.replace("sqlite:///", ""))
        return None
    
    # 🆕 Cache-related helper methods
    def get_cache_path(self) -> Path:
        """Get cache database path"""
        return Path(self.CACHE_PATH)
    
    @property
    def cache_enabled_with_fallback(self) -> bool:
        """Check if caching and fallback are both enabled"""
        return self.CACHE_ENABLED and self.ENSEMBL_ENABLED


# Global settings instance
settings = Settings()
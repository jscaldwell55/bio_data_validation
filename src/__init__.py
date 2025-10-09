from src.monitoring.logging_config import setup_logging
from config.base_config import settings

def initialize_monitoring():
    """Initialize all monitoring components on application startup"""
    # Setup structured logging
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_file="logs/validation.log",
        enable_json=(settings.LOG_FORMAT == "json")
    )
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Monitoring initialized for {settings.ENVIRONMENT} environment")
    logger.info(f"Log level: {settings.LOG_LEVEL}, Format: {settings.LOG_FORMAT}")

# Call this at application startup
initialize_monitoring()
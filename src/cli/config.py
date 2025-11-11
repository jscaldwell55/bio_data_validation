"""Configuration file management for validate-bio CLI"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for validate-bio CLI"""

    DEFAULT_CONFIG = {
        "version": "1.0",
        "api": {
            "ncbi": {
                "key": None,
                "rate_limit": 10
            },
            "ensembl": {
                "enabled": True,
                "rate_limit": 15
            }
        },
        "cache": {
            "enabled": True,
            "path": "~/.validate-bio/cache.db",
            "ttl_hours": 168,  # 7 days
            "max_size_mb": 100
        },
        "validation": {
            "default_organism": "human",
            "default_missing_threshold": 0.10,
            "default_outlier_threshold": 5.0,
            "auto_detect_type": True
        },
        "output": {
            "default_format": "text",
            "color": True,
            "verbose": False,
            "save_reports": False,
            "report_directory": "validation_reports"
        },
        "performance": {
            "parallel_workers": 4,
            "batch_size": 50
        }
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config manager.

        Args:
            config_path: Path to config file. If None, uses ~/.validate-bio/config.yml
        """
        if config_path is None:
            config_path = Path.home() / ".validate-bio" / "config.yml"

        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent
        self._config = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load config from file, creating default if needed"""
        if not self.config_path.exists():
            logger.info(f"Config file not found, creating default: {self.config_path}")
            self._ensure_dir()
            self._save(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.debug(f"Loaded config from {self.config_path}")

            # Merge with defaults for any missing keys
            return self._merge_with_defaults(config)

        except Exception as e:
            logger.warning(f"Error loading config: {e}. Using defaults.")
            return self.DEFAULT_CONFIG.copy()

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user config with defaults"""
        merged = self.DEFAULT_CONFIG.copy()

        def deep_merge(base: dict, override: dict):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value

        deep_merge(merged, config)
        return merged

    def _save(self, config: Dict[str, Any]):
        """Save config to file"""
        self._ensure_dir()

        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.debug(f"Saved config to {self.config_path}")

    def _ensure_dir(self):
        """Ensure config directory exists"""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get config value by path.

        Args:
            *keys: Path to value (e.g., 'api', 'ncbi', 'key')
            default: Default value if not found

        Returns:
            Config value or default

        Example:
            >>> config.get('api', 'ncbi', 'key')
            'your_api_key'
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys_and_value):
        """
        Set config value by path.

        Args:
            *keys_and_value: Path to value followed by the value

        Example:
            >>> config.set('api', 'ncbi', 'key', 'my_new_key')
        """
        if len(keys_and_value) < 2:
            raise ValueError("Must provide at least key and value")

        keys = keys_and_value[:-1]
        value = keys_and_value[-1]

        # Navigate to parent dict
        current = self._config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set value
        current[keys[-1]] = value

        # Save to disk
        self._save(self._config)
        logger.debug(f"Set config: {'.'.join(keys)} = {value}")

    def has_api_key(self) -> bool:
        """Check if NCBI API key is configured"""
        key = self.get('api', 'ncbi', 'key')
        return key is not None and key != ""

    def get_cache_path(self) -> Path:
        """Get cache database path"""
        cache_path = self.get('cache', 'path', default='~/.validate-bio/cache.db')
        return Path(cache_path).expanduser()

    def is_cache_enabled(self) -> bool:
        """Check if cache is enabled"""
        return self.get('cache', 'enabled', default=True)

    def to_dict(self) -> Dict[str, Any]:
        """Get config as dictionary"""
        return self._config.copy()


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from file.

    Args:
        config_path: Path to config file. If None, uses default location

    Returns:
        Config instance
    """
    return Config(config_path)

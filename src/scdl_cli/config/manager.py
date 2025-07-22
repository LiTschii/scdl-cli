"""Configuration management for scdl-cli."""

import toml
from pathlib import Path
from typing import Dict, Any, Optional
import os


class ConfigManager:
    """Manages configuration for scdl-cli."""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Default config location
            config_dir = Path.home() / '.config' / 'scdl-cli'
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / 'config.toml'
        
        self.data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return toml.load(f)
            except Exception:
                pass  # Fall back to defaults
        
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'output_dir': str(Path.home() / 'Downloads' / 'scdl'),
            'format': 'mp3',
            'quality': 'best',
            'client_id': '',
            'concurrent_downloads': 3,
            'timeout': 3600,
            'verbose': False,
            'sync': {
                'remove_deleted': True,  # Remove tracks no longer in playlist
                'update_metadata': False,  # Re-download for metadata updates
                'original_art': True,  # Download original artwork
                'original_name': True  # Keep original file names
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        # Check environment variables first
        env_key = f"SCDL_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        return self.data.get(key, default)
    
    def get_client_id(self) -> Optional[str]:
        """Get client ID with auto-generation fallback."""
        # Check environment variables first
        env_value = os.getenv('SCDL_CLIENT_ID')
        if env_value:
            return env_value
        
        # Check stored config
        stored_value = self.data.get('client_id')
        if stored_value:
            return stored_value
        
        # Auto-generate if not found
        from ..utils.client_id import ClientIDManager
        client_manager = ClientIDManager()  # Don't pass self to avoid recursion
        auto_id = client_manager.auto_generate_client_id()
        if auto_id:
            return auto_id
        
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.data[key] = value
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration with dictionary."""
        self.data.update(config_dict)
    
    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            toml.dump(self.data, f)
    
    def reset(self) -> None:
        """Reset configuration to defaults."""
        self.data = self._get_default_config()
        self.save()
    
    def get_config_path(self) -> str:
        """Get configuration file path."""
        return str(self.config_path)
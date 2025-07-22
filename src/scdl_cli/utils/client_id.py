"""Client ID auto-generation utilities for scdl-cli."""

import re
import requests
from typing import Optional
import logging
from pathlib import Path
import json
import time


class ClientIDManager:
    """Manages SoundCloud client ID auto-generation and caching."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cache_file = Path.home() / '.config' / 'scdl-cli' / 'client_id_cache.json'
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    def auto_generate_client_id(self) -> Optional[str]:
        """Auto-generate a client ID without config dependencies."""
        # 1. Try cached auto-generated client ID
        cached_id = self._get_cached_client_id()
        if cached_id and self._is_valid_client_id(cached_id):
            return cached_id
        
        # 2. Auto-generate new client ID
        auto_id = self._auto_generate_client_id()
        if auto_id:
            self._cache_client_id(auto_id)
            return auto_id
        
        return None
    
    def _get_cached_client_id(self) -> Optional[str]:
        """Get cached client ID if still valid."""
        try:
            if not self.cache_file.exists():
                return None
            
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is not too old (24 hours)
            cache_time = cache_data.get('timestamp', 0)
            if time.time() - cache_time > 86400:  # 24 hours
                return None
            
            return cache_data.get('client_id')
        except Exception as e:
            self.logger.debug(f"Failed to read cached client ID: {e}")
            return None
    
    def _cache_client_id(self, client_id: str) -> None:
        """Cache the client ID for future use."""
        try:
            cache_data = {
                'client_id': client_id,
                'timestamp': time.time()
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            self.logger.debug(f"Failed to cache client ID: {e}")
    
    def _auto_generate_client_id(self) -> Optional[str]:
        """Auto-generate client ID by extracting from SoundCloud web client."""
        self.logger.info("Attempting to auto-generate client ID...")
        
        # Method 1: Extract from SoundCloud homepage
        client_id = self._extract_from_homepage()
        if client_id:
            return client_id
        
        # Method 2: Extract from known API endpoints
        client_id = self._extract_from_api_calls()
        if client_id:
            return client_id
        
        self.logger.warning("Failed to auto-generate client ID")
        return None
    
    def _extract_from_homepage(self) -> Optional[str]:
        """Extract client ID from SoundCloud homepage JavaScript."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get('https://soundcloud.com', headers=headers, timeout=10)
            if response.status_code != 200:
                return None
            
            # Look for client_id in the page source
            patterns = [
                r'client_id["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32})["\']',
                r'client_id=([a-zA-Z0-9]{32})',
                r'"client_id":"([a-zA-Z0-9]{32})"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    client_id = matches[0]
                    self.logger.info(f"Extracted client ID from homepage: {client_id[:8]}...")
                    return client_id
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to extract client ID from homepage: {e}")
            return None
    
    def _extract_from_api_calls(self) -> Optional[str]:
        """Extract client ID from SoundCloud API calls."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Try to fetch a public track page and look for API calls
            response = requests.get('https://soundcloud.com/discover', headers=headers, timeout=10)
            if response.status_code != 200:
                return None
            
            # Look for API URLs with client_id parameter
            api_pattern = r'api(?:-v2)?\.soundcloud\.com[^"\']*client_id=([a-zA-Z0-9]{32})'
            matches = re.findall(api_pattern, response.text)
            
            if matches:
                client_id = matches[0]
                self.logger.info(f"Extracted client ID from API calls: {client_id[:8]}...")
                return client_id
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Failed to extract client ID from API calls: {e}")
            return None
    
    def _is_valid_client_id(self, client_id: str) -> bool:
        """Validate client ID by testing it against SoundCloud API."""
        if not client_id or len(client_id) != 32:
            return False
        
        try:
            # Test the client ID with a simple API call
            test_url = f"https://api-v2.soundcloud.com/resolve?url=https://soundcloud.com/discover&client_id={client_id}"
            response = requests.get(test_url, timeout=5)
            
            # Valid if we don't get 401/403 errors
            return response.status_code not in [401, 403]
            
        except Exception:
            return False
    
    def clear_cache(self) -> None:
        """Clear cached client ID."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                self.logger.info("Cleared client ID cache")
        except Exception as e:
            self.logger.debug(f"Failed to clear cache: {e}")
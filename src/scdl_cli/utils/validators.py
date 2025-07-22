"""Validation utilities for scdl-cli."""

import re
from urllib.parse import urlparse


def validate_url(url: str) -> bool:
    """Validate if URL is a valid SoundCloud URL."""
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Check if it's a SoundCloud URL
        soundcloud_patterns = [
            r'^(www\.)?soundcloud\.com/.+',
            r'^m\.soundcloud\.com/.+',  # Mobile URLs
            r'^on\.soundcloud\.com/.+',  # Short URLs
        ]
        
        domain_with_path = f"{parsed.netloc}{parsed.path}"
        return any(re.match(pattern, domain_with_path) for pattern in soundcloud_patterns)
        
    except Exception:
        return False


def validate_client_id(client_id: str) -> bool:
    """Validate SoundCloud client ID format."""
    if not client_id:
        return False
    
    # Basic validation - SoundCloud client IDs are typically alphanumeric
    return re.match(r'^[a-zA-Z0-9_-]+$', client_id) is not None


def validate_output_path(path: str) -> bool:
    """Validate output path."""
    if not path:
        return False
    
    try:
        # Check if path contains invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        return not any(char in path for char in invalid_chars)
    except Exception:
        return False
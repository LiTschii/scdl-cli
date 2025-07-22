"""Core downloader functionality wrapping scdl."""

import subprocess
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import shlex
import logging

from ..utils.validators import validate_url


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    files_count: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None


class ScdlWrapper:
    """Wrapper class for scdl functionality."""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
    
    def download(self, **options) -> DownloadResult:
        """Download a single URL using scdl."""
        url = options.get('url')
        if not validate_url(url):
            return DownloadResult(success=False, error="Invalid URL format")
        
        # Build scdl command
        cmd = self._build_scdl_command(options)
        
        try:
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                # Count downloaded files (basic heuristic)
                files_count = self._count_output_files(options.get('output_dir', './downloads'))
                return DownloadResult(
                    success=True,
                    files_count=files_count,
                    output_path=options.get('output_dir')
                )
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return DownloadResult(success=False, error=error_msg)
                
        except subprocess.TimeoutExpired:
            return DownloadResult(success=False, error="Download timeout")
        except FileNotFoundError:
            return DownloadResult(success=False, error="scdl not found. Please install scdl first.")
        except Exception as e:
            return DownloadResult(success=False, error=str(e))
    
    def batch_download(self, urls: List[str], **options) -> DownloadResult:
        """Download multiple URLs concurrently."""
        concurrent_count = options.pop('concurrent', 3)
        successful_downloads = 0
        total_files = 0
        errors = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            future_to_url = {
                executor.submit(self.download, url=url, **options): url 
                for url in urls
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result.success:
                        successful_downloads += 1
                        total_files += result.files_count
                    else:
                        errors.append(f"{url}: {result.error}")
                except Exception as e:
                    errors.append(f"{url}: {str(e)}")
        
        if successful_downloads == 0:
            return DownloadResult(
                success=False, 
                error=f"All downloads failed. Errors: {'; '.join(errors)}"
            )
        
        success = successful_downloads == len(urls)
        error = None if success else f"Partial success. Errors: {'; '.join(errors)}"
        
        return DownloadResult(
            success=success,
            files_count=total_files,
            error=error
        )
    
    def _build_scdl_command(self, options: Dict[str, Any]) -> List[str]:
        """Build scdl command from options."""
        cmd = ['scdl']
        
        # URL (required)
        if 'url' in options:
            cmd.extend(['-l', options['url']])
        
        # Output directory
        if 'output_dir' in options:
            output_path = Path(options['output_dir']).expanduser().absolute()
            output_path.mkdir(parents=True, exist_ok=True)
            cmd.extend(['--path', str(output_path)])
        
        # Client ID
        client_id = options.get('client_id') or self.config.get('client_id')
        if client_id:
            cmd.extend(['--client-id', client_id])
        
        # Download type flags
        if options.get('playlist'):
            cmd.append('--playlist')
        elif options.get('all_tracks'):
            cmd.append('--all')
        elif options.get('favorites'):
            cmd.append('--favorites')
        
        # Audio format and quality
        if options.get('format'):
            cmd.extend(['--original-art', '--original-name'])
        
        # Verbose mode
        if options.get('verbose'):
            cmd.append('--verbose')
        
        return cmd
    
    def _count_output_files(self, output_dir: str) -> int:
        """Count files in output directory (basic heuristic)."""
        try:
            path = Path(output_dir)
            if path.exists():
                # Count audio files
                audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
                return len([f for f in path.rglob('*') if f.suffix.lower() in audio_extensions])
            return 0
        except Exception:
            return 0
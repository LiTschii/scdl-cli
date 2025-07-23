"""Playlist synchronization functionality."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from ..utils.validators import validate_url


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    files_count: int = 0
    error: Optional[str] = None


class PlaylistSync:
    """Manages playlist-directory mappings and synchronization."""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Store playlist mappings in config directory
        config_dir = Path.home() / '.config' / 'scdl-cli'
        config_dir.mkdir(parents=True, exist_ok=True)
        self.mappings_file = config_dir / 'playlists.json'
        
        self._load_mappings()
    
    def _load_mappings(self) -> None:
        """Load playlist mappings from file."""
        try:
            if self.mappings_file.exists():
                with open(self.mappings_file, 'r') as f:
                    self.mappings = json.load(f)
            else:
                self.mappings = {}
        except Exception as e:
            self.logger.error(f"Failed to load mappings: {e}")
            self.mappings = {}
    
    def _save_mappings(self) -> None:
        """Save playlist mappings to file."""
        try:
            with open(self.mappings_file, 'w') as f:
                json.dump(self.mappings, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save mappings: {e}")
    
    def add_playlist(self, playlist_url: str, directory: str) -> SyncResult:
        """Add a playlist-directory mapping."""
        if not validate_url(playlist_url):
            return SyncResult(success=False, error="Invalid playlist URL")
        
        # Ensure it's a playlist URL
        if '/sets/' not in playlist_url:
            return SyncResult(success=False, error="URL must be a playlist (contains '/sets/')")
        
        # Create directory if it doesn't exist
        dir_path = Path(directory).expanduser().absolute()
        
        # Just show info about shared vs private storage
        termux_shared_paths = ['/storage/emulated/', '/sdcard/', '/storage/']
        is_shared_storage = any(str(dir_path).startswith(path) for path in termux_shared_paths)
        is_termux = Path('/data/data/com.termux').exists()
        
        if is_shared_storage and is_termux:
            print(f"📱 Downloading to Android shared storage: {dir_path}")
            print(f"   Files will be accessible to music players and other Android apps.")
            print(f"   Note: May encounter file locking issues on some systems.")
        elif is_termux:
            print(f"📁 Downloading to Termux private storage: {dir_path}")
            print(f"   Files will not be accessible to other Android apps.")
        
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return SyncResult(success=False, error=f"Cannot create directory: {e}")
        
        # Add mapping
        self.mappings[playlist_url] = {
            'directory': str(dir_path),
            'added_date': datetime.now().isoformat(),
            'last_sync': None
        }
        
        self._save_mappings()
        return SyncResult(success=True)
    
    def remove_playlist(self, playlist_url: str) -> SyncResult:
        """Remove a playlist from mappings."""
        if playlist_url not in self.mappings:
            return SyncResult(success=False, error="Playlist not found in mappings")
        
        del self.mappings[playlist_url]
        self._save_mappings()
        return SyncResult(success=True)
    
    def list_playlists(self) -> List[Dict[str, str]]:
        """List all configured playlist mappings."""
        result = []
        for url, data in self.mappings.items():
            result.append({
                'url': url,
                'directory': data['directory'],
                'last_sync': data.get('last_sync', 'Never')
            })
        return result
    
    def sync_playlist(self, playlist_url: str, dry_run: bool = False) -> SyncResult:
        """Sync a specific playlist."""
        if playlist_url not in self.mappings:
            return SyncResult(success=False, error="Playlist not found in mappings")
        
        mapping = self.mappings[playlist_url]
        directory = mapping['directory']
        archive_file = Path(directory) / 'scdl_archive.txt'
        
        # Ensure directory exists with proper permissions
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        
        
        # Check if archive file exists and is valid
        is_first_sync = not archive_file.exists()
        
        # If archive file exists but is empty or corrupted, treat as first sync
        if archive_file.exists():
            try:
                if archive_file.stat().st_size == 0:
                    if self.config.get('debug', False):
                        print(f"🐛 DEBUG: Archive file is empty, treating as first sync")
                    is_first_sync = True
                elif archive_file.stat().st_size < 10:  # Very small files are likely corrupted
                    if self.config.get('debug', False):
                        print(f"🐛 DEBUG: Archive file is too small ({archive_file.stat().st_size} bytes), recreating")
                    archive_file.unlink()  # Remove corrupted file
                    is_first_sync = True
            except Exception as e:
                if self.config.get('debug', False):
                    print(f"🐛 DEBUG: Error checking archive file: {e}, treating as first sync")
                is_first_sync = True
        
        if dry_run:
            return SyncResult(success=True, files_count=0)
        
        try:
            if is_first_sync:
                # First sync: just download everything with archive tracking
                cmd = self._build_initial_sync_command(playlist_url, directory)
                self.logger.info(f"First sync, executing: {' '.join(cmd)}")
            else:
                # Subsequent syncs: use --sync for proper synchronization
                cmd = self._build_sync_command(playlist_url, directory)
                self.logger.info(f"Sync update, executing: {' '.join(cmd)}")
            
            # Don't wrap scdl command with su - it won't have access to Termux packages
            # Instead, we'll use su only for specific file operations that need root permissions
            
            # Show clean progress or debug info
            if self.config.get('debug', False):
                print(f"\n🐛 DEBUG: Executing command: {' '.join(cmd)}")
            else:
                # Show clean progress without debug noise
                print(f"🔄 Downloading tracks from playlist...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Show output when debug is enabled
            if self.config.get('debug', False):
                print(f"🐛 DEBUG: Return code: {result.returncode}")
                if result.stdout:
                    print(f"🐛 DEBUG: STDOUT:\n{result.stdout}")
                if result.stderr:
                    print(f"🐛 DEBUG: STDERR:\n{result.stderr}")
            
            
            if result.returncode == 0:
                # Add track URLs to metadata if we have them
                try:
                    self._add_track_urls_to_metadata(directory, result.stderr or "")
                except Exception as e:
                    if self.config.get('debug', False):
                        print(f"🐛 DEBUG: Failed to add URLs to metadata: {e}")
                
                # Update last sync time
                self.mappings[playlist_url]['last_sync'] = datetime.now().isoformat()
                self._save_mappings()
                
                # Count new files (basic heuristic)
                files_count = self._count_new_files(directory)
                
                # Check if files were skipped due to locking issues
                stderr_text = result.stderr or ""
                if "Could not acquire lock" in stderr_text and "Skipping" in stderr_text:
                    skipped_count = stderr_text.count("Skipping")
                    if skipped_count > 0:
                        print(f"⚠️  {skipped_count} files were skipped due to file locking issues")
                        print(f"   Try running 'scli clean' and then sync again")
                
                return SyncResult(success=True, files_count=files_count)
            else:
                # Check for file locking errors and provide helpful message
                error_msg = result.stderr or result.stdout or "Unknown error"
                if "Could not acquire lock" in error_msg:
                    error_msg = ("File locking error detected. This can happen with shared storage.\n"
                               f"Try: 1) Run 'scli clean' to remove corrupted archives\n"
                               f"     2) Use a private storage path like $HOME/Music/scdl\n"
                               f"     3) Or retry the sync - sometimes it works on second try")
                
                return SyncResult(success=False, error=error_msg)
                
        except subprocess.TimeoutExpired:
            return SyncResult(success=False, error="Sync timeout")
        except FileNotFoundError:
            return SyncResult(success=False, error="scdl not found. Please install scdl first.")
        except Exception as e:
            return SyncResult(success=False, error=str(e))
    
    def sync_all(self, dry_run: bool = False) -> Dict[str, SyncResult]:
        """Sync all configured playlists."""
        results = {}
        for playlist_url in self.mappings.keys():
            results[playlist_url] = self.sync_playlist(playlist_url, dry_run=dry_run)
        return results
    
    def _build_sync_command(self, playlist_url: str, directory: str) -> List[str]:
        """Build scdl command for playlist sync."""
        cmd = ['scdl']
        
        # Playlist URL
        cmd.extend(['-l', playlist_url])
        
        # Output directory
        cmd.extend(['--path', directory])
        
        # Client ID
        client_id = self.config.get_client_id()
        if client_id:
            cmd.extend(['--client-id', client_id])
        
        # Archive file for tracking downloads
        archive_file = Path(directory) / 'scdl_archive.txt'
        
        # Use only --sync flag which handles archive internally
        cmd.extend(['--sync', str(archive_file)])
        
        # Always enable debug to capture track URLs for metadata
        cmd.append('--debug')
        
        # Add sync behavior configuration
        sync_config = self.config.get('sync', {})
        
        # Original artwork and naming
        if sync_config.get('original_art', True):
            cmd.append('--original-art')
        if sync_config.get('original_name', True):
            cmd.append('--original-name')
        
        # Always force metadata to ensure artwork is embedded
        cmd.append('--force-metadata')
        
        # Add artist to filename if missing (helps with organization)
        cmd.append('--addtofile')
        
        # Audio format
        format_type = self.config.get('format', 'mp3')
        if format_type == 'flac':
            cmd.append('--flac')
        elif format_type == 'opus':
            cmd.append('--opus')
        # mp3 is default, no flag needed
        
        return cmd
    
    def _build_initial_sync_command(self, playlist_url: str, directory: str) -> List[str]:
        """Build scdl command for initial playlist download (no --sync flag)."""
        cmd = ['scdl']
        
        # Playlist URL
        cmd.extend(['-l', playlist_url])
        
        # Output directory
        cmd.extend(['--path', directory])
        
        # Client ID
        client_id = self.config.get_client_id()
        if client_id:
            cmd.extend(['--client-id', client_id])
        
        # Archive file for tracking downloads (first run creates the archive)
        archive_file = Path(directory) / 'scdl_archive.txt'
        cmd.extend(['--download-archive', str(archive_file)])
        
        # Always enable debug to capture track URLs for metadata
        cmd.append('--debug')
        
        # Add sync behavior configuration
        sync_config = self.config.get('sync', {})
        
        # Original artwork and naming
        if sync_config.get('original_art', True):
            cmd.append('--original-art')
        if sync_config.get('original_name', True):
            cmd.append('--original-name')
        
        # Always force metadata to ensure artwork is embedded
        cmd.append('--force-metadata')
        
        # Add artist to filename if missing (helps with organization)
        cmd.append('--addtofile')
        
        # Audio format
        format_type = self.config.get('format', 'mp3')
        if format_type == 'flac':
            cmd.append('--flac')
        elif format_type == 'opus':
            cmd.append('--opus')
        # mp3 is default, no flag needed
        
        return cmd
    
    
    def _count_new_files(self, directory: str) -> int:
        """Count newly downloaded files by comparing with archive."""
        try:
            path = Path(directory)
            if not path.exists():
                return 0
            
            # Get list of files from archive to see what should have been downloaded
            archive_file = path / 'scdl_archive.txt'
            if not archive_file.exists():
                # No archive file, count all audio files as new
                audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus'}
                return len([f for f in path.rglob('*') if f.is_file() and f.suffix.lower() in audio_extensions])
            
            # Count files modified in the last 5 minutes (more reasonable than 1 minute)
            import time
            current_time = time.time()
            recent_threshold = current_time - 300  # 5 minutes ago
            
            audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus'}
            recent_files = []
            
            for file_path in path.rglob('*'):
                if (file_path.is_file() and 
                    file_path.suffix.lower() in audio_extensions and 
                    file_path.stat().st_mtime > recent_threshold):
                    recent_files.append(file_path)
            
            return len(recent_files)
        except Exception:
            return 0
    
    def _add_track_urls_to_metadata(self, directory: str, scdl_output: str) -> None:
        """Extract track URLs from scdl output and add them to metadata under composer field."""
        try:
            import re
            from pathlib import Path
            
            # Find track URLs and titles in the scdl debug output
            # Look for lines like "Downloading [Track Title]" followed by track info
            url_pattern = r"permalink_url='([^']*soundcloud\.com/[^']*)'"
            title_pattern = r"title='([^']*?)'"
            
            # Extract URL and title pairs
            urls = re.findall(url_pattern, scdl_output)
            titles = re.findall(title_pattern, scdl_output)
            
            if not urls:
                return
            
            # Create a mapping of cleaned titles to URLs
            title_url_map = {}
            for i, (url, title) in enumerate(zip(urls, titles)):
                # Clean title for filename matching
                clean_title = self._clean_filename(title)
                title_url_map[clean_title] = url
                
                if self.config.get('debug', False):
                    print(f"🔗 Found track: {title} -> {url}")
            
            # Find recently downloaded audio files and add URLs to metadata
            path = Path(directory)
            if not path.exists():
                return
            
            audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus'}
            
            # Look for recent files (last 5 minutes)
            import time
            current_time = time.time()
            recent_threshold = current_time - 300
            
            for file_path in path.rglob('*'):
                if (file_path.is_file() and 
                    file_path.suffix.lower() in audio_extensions and 
                    file_path.stat().st_mtime > recent_threshold):
                    
                    # Try to match filename to title
                    filename_base = file_path.stem.lower()
                    matched_url = None
                    
                    # Find the best matching URL for this file
                    for clean_title, url in title_url_map.items():
                        if clean_title.lower() in filename_base:
                            matched_url = url
                            break
                    
                    if matched_url:
                        self._add_url_to_file_metadata(file_path, matched_url)
                        if self.config.get('debug', False):
                            print(f"🔗 Added URL to {file_path.name}")
                        
        except Exception as e:
            if self.config.get('debug', False):
                print(f"🐛 DEBUG: Error in URL extraction: {e}")
    
    def _clean_filename(self, title: str) -> str:
        """Clean title for filename matching."""
        import re
        # Remove characters that are typically removed from filenames
        cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def _add_url_to_file_metadata(self, file_path: Path, url: str) -> None:
        """Add SoundCloud URL to file metadata under composer field."""
        try:
            # Try to import mutagen for metadata editing
            from mutagen import File
            from mutagen.id3 import ID3, TCOM
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
            
            audio_file = File(file_path)
            if audio_file is None:
                return
            
            # Handle different file formats
            if file_path.suffix.lower() == '.mp3':
                # MP3 files - use ID3 tags
                if audio_file.tags is None:
                    audio_file.add_tags()
                audio_file.tags.add(TCOM(encoding=3, text=[url]))
                
            elif file_path.suffix.lower() == '.m4a':
                # M4A files - use MP4 tags
                audio_file['\xa9wrt'] = [url]  # Composer field in MP4
                
            elif file_path.suffix.lower() == '.flac':
                # FLAC files
                audio_file['COMPOSER'] = url
                
            else:
                # Try generic approach for other formats
                if hasattr(audio_file, 'tags') and audio_file.tags:
                    audio_file.tags['COMPOSER'] = url
            
            audio_file.save()
            
        except ImportError:
            # mutagen not available - skip metadata editing
            if self.config.get('debug', False):
                print(f"🐛 DEBUG: mutagen not available for metadata editing")
        except Exception as e:
            if self.config.get('debug', False):
                print(f"🐛 DEBUG: Error adding URL to {file_path.name}: {e}")
    

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
        
        # Handle Android shared storage with symlink workaround
        termux_shared_paths = ['/storage/emulated/', '/sdcard/', '/storage/']
        is_shared_storage = any(str(dir_path).startswith(path) for path in termux_shared_paths)
        is_termux = Path('/data/data/com.termux').exists()
        
        if is_shared_storage and is_termux:
            # Create a private storage location for actual downloads
            private_dir = Path.home() / 'Music' / 'scdl-downloads' / dir_path.name
            private_dir.mkdir(parents=True, exist_ok=True)
            
            # Create the shared storage directory if it doesn't exist
            dir_path.mkdir(parents=True, exist_ok=True)
            
            print(f"🔗 ANDROID SHARED STORAGE DETECTED")
            print(f"   Downloads will happen in private storage: {private_dir}")
            print(f"   Music files will be symlinked to shared storage: {dir_path}")
            print(f"   This avoids file locking issues while keeping music accessible to Android apps.")
            
            # Update the directory to use private storage for scdl
            directory = str(private_dir)
            
            # Store both paths for later symlinking
            self._shared_storage_path = dir_path
            self._private_storage_path = private_dir
        
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
            
            # Show command and output when debug is enabled
            if self.config.get('debug', False):
                print(f"\n🐛 DEBUG: Executing command: {' '.join(cmd)}")
            
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
                # Create symlinks if using shared storage workaround
                if hasattr(self, '_shared_storage_path') and hasattr(self, '_private_storage_path'):
                    self._create_symlinks_to_shared_storage()
                
                # Update last sync time
                self.mappings[playlist_url]['last_sync'] = datetime.now().isoformat()
                self._save_mappings()
                
                # Count new files (basic heuristic)
                files_count = self._count_new_files(directory)
                
                
                return SyncResult(success=True, files_count=files_count)
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
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
        
        # Add debug flag if enabled
        if self.config.get('debug', False):
            cmd.append('--debug')
        
        # Add sync behavior configuration
        sync_config = self.config.get('sync', {})
        
        # Original artwork and naming
        if sync_config.get('original_art', True):
            cmd.append('--original-art')
        if sync_config.get('original_name', True):
            cmd.append('--original-name')
        
        # Metadata handling
        if sync_config.get('update_metadata', False):
            cmd.append('--force-metadata')
        
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
        
        # Add debug flag if enabled
        if self.config.get('debug', False):
            cmd.append('--debug')
        
        # Add sync behavior configuration
        sync_config = self.config.get('sync', {})
        
        # Original artwork and naming
        if sync_config.get('original_art', True):
            cmd.append('--original-art')
        if sync_config.get('original_name', True):
            cmd.append('--original-name')
        
        # Metadata handling
        if sync_config.get('update_metadata', False):
            cmd.append('--force-metadata')
        
        # Audio format
        format_type = self.config.get('format', 'mp3')
        if format_type == 'flac':
            cmd.append('--flac')
        elif format_type == 'opus':
            cmd.append('--opus')
        # mp3 is default, no flag needed
        
        return cmd
    
    
    def _count_new_files(self, directory: str) -> int:
        """Count recently downloaded files (basic heuristic)."""
        try:
            path = Path(directory)
            if not path.exists():
                return 0
            
            # Count audio files modified in the last minute
            # This is a simple heuristic for newly downloaded files
            import time
            current_time = time.time()
            recent_threshold = current_time - 60  # 1 minute ago
            
            audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
            recent_files = []
            
            for file_path in path.rglob('*'):
                if (file_path.suffix.lower() in audio_extensions and 
                    file_path.stat().st_mtime > recent_threshold):
                    recent_files.append(file_path)
            
            return len(recent_files)
        except Exception:
            return 0
    
    def _create_symlinks_to_shared_storage(self) -> None:
        """Create symlinks from private storage to shared storage for Android access."""
        try:
            private_path = self._private_storage_path
            shared_path = self._shared_storage_path
            
            if not private_path.exists():
                return
            
            # Find all audio files in private storage
            audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus'}
            
            for file_path in private_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                    # Calculate relative path from private storage root
                    relative_path = file_path.relative_to(private_path)
                    shared_file_path = shared_path / relative_path
                    
                    # Create parent directories in shared storage if needed
                    shared_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Create symlink if it doesn't exist or points to wrong file
                    if not shared_file_path.exists() or (shared_file_path.is_symlink() and shared_file_path.readlink() != file_path):
                        # Remove existing symlink/file if it exists
                        if shared_file_path.exists() or shared_file_path.is_symlink():
                            shared_file_path.unlink()
                        
                        # Create the symlink
                        shared_file_path.symlink_to(file_path)
                        
                        if self.config.get('debug', False):
                            print(f"🔗 Created symlink: {shared_file_path} → {file_path}")
            
            print(f"✅ Music files are now accessible to Android apps in: {shared_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create symlinks to shared storage: {e}")
            if self.config.get('debug', False):
                print(f"🐛 DEBUG: Symlink error: {e}")
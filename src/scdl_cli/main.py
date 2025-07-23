"""Main CLI interface for scdl-cli playlist synchronization."""

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
from typing import Optional

from .core.sync import PlaylistSync
from .config.manager import ConfigManager

console = Console()


@click.group()
@click.version_option()
@click.pass_context
def main(ctx: click.Context) -> None:
    """Playlist synchronization tool for SoundCloud downloads using scdl."""
    ctx.ensure_object(dict)
    ctx.obj['config'] = ConfigManager()
    ctx.obj['sync'] = PlaylistSync(ctx.obj['config'])


@main.command()
@click.argument('playlist_url')
@click.argument('directory', type=click.Path())
@click.pass_context
def add(ctx: click.Context, playlist_url: str, directory: str) -> None:
    """Add a playlist-directory mapping for synchronization."""
    sync = ctx.obj['sync']
    
    try:
        result = sync.add_playlist(playlist_url, directory)
        if result.success:
            console.print(f"✅ Added playlist mapping: {playlist_url} → {directory}", style="green")
        else:
            console.print(f"❌ Failed to add playlist: {result.error}", style="red")
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")


@main.command()
@click.argument('playlist_url')
@click.pass_context
def remove(ctx: click.Context, playlist_url: str) -> None:
    """Remove a playlist from synchronization."""
    sync = ctx.obj['sync']
    
    try:
        result = sync.remove_playlist(playlist_url)
        if result.success:
            console.print(f"✅ Removed playlist: {playlist_url}", style="green")
        else:
            console.print(f"❌ Failed to remove playlist: {result.error}", style="red")
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")


@main.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """List all configured playlist-directory mappings."""
    sync = ctx.obj['sync']
    
    playlists = sync.list_playlists()
    
    if not playlists:
        console.print("📭 No playlists configured", style="yellow")
        return
    
    table = Table(title="Configured Playlists")
    table.add_column("Playlist URL", style="blue")
    table.add_column("Directory", style="green")
    table.add_column("Last Sync", style="dim")
    
    for playlist in playlists:
        last_sync = playlist.get('last_sync', 'Never')
        table.add_row(playlist['url'], playlist['directory'], last_sync)
    
    console.print(table)


@main.command()
@click.option('--playlist', help='Sync specific playlist URL only')
@click.option('--dry-run', is_flag=True, help='Show what would be downloaded without downloading')
@click.option('--debug', is_flag=True, help='Enable debug output')
@click.pass_context
def sync(ctx: click.Context, playlist: Optional[str], dry_run: bool, debug: bool) -> None:
    """Synchronize all configured playlists or a specific one."""
    sync_manager = ctx.obj['sync']
    
    if playlist:
        console.print(f"🔄 Syncing playlist: {playlist}", style="blue")
        playlists_to_sync = [playlist]
    else:
        playlists = sync_manager.list_playlists()
        if not playlists:
            console.print("📭 No playlists configured. Use 'add' command first.", style="yellow")
            return
        console.print(f"🔄 Syncing {len(playlists)} playlist(s)", style="blue")
        playlists_to_sync = [p['url'] for p in playlists]
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Synchronizing...", total=len(playlists_to_sync))
            
            for playlist_url in playlists_to_sync:
                progress.update(task, description=f"Syncing {playlist_url}")
                # Override config debug setting if command line flag is provided
                if debug:
                    sync_manager.config.set('debug', True)
                result = sync_manager.sync_playlist(playlist_url, dry_run=dry_run)
                
                if result.success:
                    if dry_run:
                        console.print(f"✅ Would download {result.files_count} new files for {playlist_url}", style="green")
                    else:
                        console.print(f"✅ Downloaded {result.files_count} new files for {playlist_url}", style="green")
                else:
                    console.print(f"❌ Sync failed for {playlist_url}: {result.error}", style="red")
                
                progress.advance(task)
            
    except KeyboardInterrupt:
        console.print("\\n❌ Sync cancelled by user", style="yellow")
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}", style="red")


@main.command()
@click.option('--client-id', help='SoundCloud client ID (optional - will auto-generate if not provided)')
@click.option('--format', help='Default audio format (mp3, flac, opus)')
@click.option('--quality', help='Default audio quality')
@click.option('--sync-remove-deleted/--no-sync-remove-deleted', default=None,
              help='Remove local tracks no longer in playlist during sync')
@click.option('--sync-update-metadata/--no-sync-update-metadata', default=None,
              help='Force metadata updates during sync')
@click.option('--sync-original-art/--no-sync-original-art', default=None,
              help='Download original artwork during sync')
@click.option('--sync-original-name/--no-sync-original-name', default=None,
              help='Keep original file names during sync')
@click.option('--debug/--no-debug', default=None,
              help='Enable debug output from scdl')
@click.pass_context
def config(
    ctx: click.Context,
    client_id: Optional[str],
    format: Optional[str],
    quality: Optional[str],
    sync_remove_deleted: Optional[bool],
    sync_update_metadata: Optional[bool],
    sync_original_art: Optional[bool],
    sync_original_name: Optional[bool],
    debug: Optional[bool]
) -> None:
    """Configure scdl-cli settings."""
    config_mgr = ctx.obj['config']
    
    # If no options provided, show current config
    options_provided = any([
        client_id is not None, format is not None, quality is not None,
        sync_remove_deleted is not None, sync_update_metadata is not None,
        sync_original_art is not None, sync_original_name is not None,
        debug is not None
    ])
    
    if not options_provided:
        console.print("📋 Current Configuration:", style="bold blue")
        console.print(f"Format: {config_mgr.get('format', 'mp3')}")
        console.print(f"Quality: {config_mgr.get('quality', 'best')}")
        console.print(f"Debug: {config_mgr.get('debug', False)}")
        sync_config = config_mgr.get('sync', {})
        console.print(f"Sync - Remove Deleted: {sync_config.get('remove_deleted', True)}")
        console.print(f"Sync - Update Metadata: {sync_config.get('update_metadata', False)}")
        console.print(f"Sync - Original Art: {sync_config.get('original_art', True)}")
        console.print(f"Sync - Original Name: {sync_config.get('original_name', True)}")
        
        client_id_display = config_mgr.get_client_id()
        if client_id_display:
            masked = client_id_display[:8] + '...' + client_id_display[-4:] if len(client_id_display) > 12 else '***'
            console.print(f"Client ID: {masked}")
        else:
            console.print("Client ID: Auto-generate (not set)")
        console.print("\n💡 Use specific flags to change settings, e.g.: scli config --debug", style="dim")
        return
    
    # Build update dict with only provided values
    config_updates = {}
    sync_updates = {}
    
    if format is not None:
        config_updates['format'] = format
    if quality is not None:
        config_updates['quality'] = quality
    if debug is not None:
        config_updates['debug'] = debug
        
    if sync_remove_deleted is not None:
        sync_updates['remove_deleted'] = sync_remove_deleted
    if sync_update_metadata is not None:
        sync_updates['update_metadata'] = sync_update_metadata
    if sync_original_art is not None:
        sync_updates['original_art'] = sync_original_art
    if sync_original_name is not None:
        sync_updates['original_name'] = sync_original_name
    
    if sync_updates:
        # Merge with existing sync config
        current_sync = config_mgr.get('sync', {})
        current_sync.update(sync_updates)
        config_updates['sync'] = current_sync
    
    # Handle client ID separately
    if client_id is not None:
        # Test the provided client ID
        from .utils.client_id import ClientIDManager
        test_manager = ClientIDManager()
        if test_manager._is_valid_client_id(client_id):
            config_updates['client_id'] = client_id
            console.print(f"✅ Using provided client ID: {client_id[:8]}...", style="green")
        else:
            console.print(f"❌ Provided client ID is invalid", style="red")
            console.print("✅ Will auto-generate client ID when needed", style="green")
    
    # Apply updates
    if config_updates:
        config_mgr.update(config_updates)
        config_mgr.save()
        console.print("✅ Configuration updated successfully", style="green")
        
        # Show what was changed
        for key, value in config_updates.items():
            if key == 'sync':
                for sync_key, sync_value in value.items():
                    console.print(f"  • Sync {sync_key}: {sync_value}", style="dim")
            else:
                console.print(f"  • {key}: {value}", style="dim")


@main.command()
@click.pass_context
def show_config(ctx: click.Context) -> None:
    """Show current configuration."""
    config = ctx.obj['config']
    
    console.print("📋 Current Configuration:", style="bold")
    for key, value in config.data.items():
        if key == 'client_id':
            # Get actual client ID (might be auto-generated)
            actual_value = config.get_client_id()
            if actual_value:
                masked_value = actual_value[:8] + '...' + actual_value[-4:] if len(actual_value) > 12 else '***'
                source = "(user-configured)" if value else "(auto-generated)"
                console.print(f"  {key}: {masked_value} {source}")
            else:
                console.print(f"  {key}: (will auto-generate when needed)")
        else:
            console.print(f"  {key}: {value}")


@main.command()
@click.pass_context
def manage(ctx: click.Context) -> None:
    """Interactive playlist management interface."""
    sync = ctx.obj['sync']
    
    while True:
        console.print("\n🎵 Playlist Management", style="bold blue")
        console.print("═" * 30)
        
        # Show current playlists
        playlists = sync.list_playlists()
        if playlists:
            console.print(f"\n📋 Current Playlists ({len(playlists)}):", style="bold")
            for i, playlist in enumerate(playlists, 1):
                # Truncate long URLs for display
                url_display = playlist['url']
                if len(url_display) > 60:
                    url_display = url_display[:57] + "..."
                
                console.print(f"  {i}. {url_display}")
                console.print(f"     → {playlist['directory']}", style="dim")
                console.print(f"     Last sync: {playlist['last_sync']}", style="dim")
        else:
            console.print("\n📭 No playlists configured", style="yellow")
        
        # Show menu options
        console.print("\n🔧 Options:", style="bold")
        console.print("  1. Add new playlist")
        console.print("  2. Remove playlist")
        console.print("  3. Change playlist directory")
        console.print("  4. Sync specific playlist")
        console.print("  5. Sync all playlists")
        console.print("  6. Exit")
        
        try:
            choice = click.prompt("\nSelect option", type=int, show_default=False)
            
            if choice == 1:
                # Add playlist
                playlist_url = click.prompt("Enter playlist URL")
                directory = click.prompt("Enter download directory", 
                                        default=str(Path.home() / 'Music' / 'scdl'))
                
                result = sync.add_playlist(playlist_url, directory)
                if result.success:
                    console.print("✅ Playlist added successfully!", style="green")
                else:
                    console.print(f"❌ Failed to add playlist: {result.error}", style="red")
            
            elif choice == 2:
                # Remove playlist
                if not playlists:
                    console.print("❌ No playlists to remove", style="red")
                    continue
                
                console.print("\n📋 Select playlist to remove:")
                for i, playlist in enumerate(playlists, 1):
                    url_display = playlist['url']
                    if len(url_display) > 70:
                        url_display = url_display[:67] + "..."
                    console.print(f"  {i}. {url_display}")
                
                try:
                    selection = click.prompt("Enter playlist number", type=int) - 1
                    if 0 <= selection < len(playlists):
                        playlist_url = playlists[selection]['url']
                        if click.confirm(f"Remove playlist: {playlist_url}?"):
                            result = sync.remove_playlist(playlist_url)
                            if result.success:
                                console.print("✅ Playlist removed successfully!", style="green")
                            else:
                                console.print(f"❌ Failed to remove playlist: {result.error}", style="red")
                    else:
                        console.print("❌ Invalid selection", style="red")
                except (ValueError, click.Abort):
                    console.print("❌ Invalid input", style="red")
            
            elif choice == 3:
                # Change directory
                if not playlists:
                    console.print("❌ No playlists configured", style="red")
                    continue
                
                console.print("\n📋 Select playlist to change directory:")
                for i, playlist in enumerate(playlists, 1):
                    url_display = playlist['url']
                    if len(url_display) > 50:
                        url_display = url_display[:47] + "..."
                    console.print(f"  {i}. {url_display}")
                    console.print(f"     Current: {playlist['directory']}", style="dim")
                
                try:
                    selection = click.prompt("Enter playlist number", type=int) - 1
                    if 0 <= selection < len(playlists):
                        playlist = playlists[selection]
                        new_directory = click.prompt("Enter new directory", 
                                                   default=playlist['directory'])
                        
                        # Remove old mapping and add new one
                        sync.remove_playlist(playlist['url'])
                        result = sync.add_playlist(playlist['url'], new_directory)
                        if result.success:
                            console.print("✅ Directory updated successfully!", style="green")
                        else:
                            console.print(f"❌ Failed to update directory: {result.error}", style="red")
                    else:
                        console.print("❌ Invalid selection", style="red")
                except (ValueError, click.Abort):
                    console.print("❌ Invalid input", style="red")
            
            elif choice == 4:
                # Sync specific playlist
                if not playlists:
                    console.print("❌ No playlists configured", style="red")
                    continue
                
                console.print("\n📋 Select playlist to sync:")
                for i, playlist in enumerate(playlists, 1):
                    url_display = playlist['url']
                    if len(url_display) > 70:
                        url_display = url_display[:67] + "..."
                    console.print(f"  {i}. {url_display}")
                
                try:
                    selection = click.prompt("Enter playlist number", type=int) - 1
                    if 0 <= selection < len(playlists):
                        playlist_url = playlists[selection]['url']
                        console.print(f"🔄 Syncing playlist...", style="blue")
                        
                        result = sync.sync_playlist(playlist_url)
                        if result.success:
                            console.print(f"✅ Downloaded {result.files_count} new files", style="green")
                        else:
                            console.print(f"❌ Sync failed: {result.error}", style="red")
                    else:
                        console.print("❌ Invalid selection", style="red")
                except (ValueError, click.Abort):
                    console.print("❌ Invalid input", style="red")
            
            elif choice == 5:
                # Sync all playlists
                if not playlists:
                    console.print("❌ No playlists configured", style="red")
                    continue
                
                console.print(f"🔄 Syncing {len(playlists)} playlist(s)...", style="blue")
                total_files = 0
                
                for playlist in playlists:
                    console.print(f"  Syncing: {playlist['url'][:50]}...", style="dim")
                    result = sync.sync_playlist(playlist['url'])
                    if result.success:
                        total_files += result.files_count
                        console.print(f"    ✅ {result.files_count} new files", style="green")
                    else:
                        console.print(f"    ❌ Failed: {result.error}", style="red")
                
                console.print(f"\n🎉 Sync complete! Total new files: {total_files}", style="bold green")
            
            elif choice == 6:
                console.print("👋 Goodbye!", style="blue")
                break
            
            else:
                console.print("❌ Invalid option. Please choose 1-6.", style="red")
                
        except (ValueError, click.Abort):
            console.print("❌ Invalid input", style="red")
        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!", style="blue")
            break


@main.command()
@click.option('--playlist', help='Clean specific playlist URL only')
@click.pass_context
def clean(ctx: click.Context, playlist: Optional[str]) -> None:
    """Clean corrupted archive files to fix sync issues."""
    sync = ctx.obj['sync']
    
    if playlist:
        playlists_to_clean = [playlist]
        console.print(f"🧹 Cleaning archive for playlist: {playlist}", style="blue")
    else:
        playlists = sync.list_playlists()
        if not playlists:
            console.print("📭 No playlists configured", style="yellow")
            return
        playlists_to_clean = [p['url'] for p in playlists]
        console.print(f"🧹 Cleaning archives for {len(playlists_to_clean)} playlist(s)", style="blue")
    
    cleaned_count = 0
    
    for playlist_url in playlists_to_clean:
        if playlist_url in sync.mappings:
            directory = sync.mappings[playlist_url]['directory']
            archive_file = Path(directory) / 'scdl_archive.txt'
            
            if archive_file.exists():
                try:
                    archive_file.unlink()
                    console.print(f"✅ Cleaned archive for: {playlist_url[:50]}...", style="green")
                    cleaned_count += 1
                except Exception as e:
                    console.print(f"❌ Failed to clean {playlist_url[:50]}...: {e}", style="red")
            else:
                console.print(f"ℹ️  No archive file found for: {playlist_url[:50]}...", style="dim")
        else:
            console.print(f"❌ Playlist not found: {playlist_url}", style="red")
    
    if cleaned_count > 0:
        console.print(f"\n🎉 Cleaned {cleaned_count} archive file(s). Next sync will be treated as first-time sync.", style="bold green")
    else:
        console.print(f"\n📭 No archive files needed cleaning.", style="yellow")


@main.command()
@click.pass_context
def setup_android(ctx: click.Context) -> None:
    """Setup Android shared storage access for music apps."""
    sync = ctx.obj['sync']
    
    # Check if we're on Termux
    if not Path('/data/data/com.termux').exists():
        console.print("❌ This command is only for Termux on Android", style="red")
        return
    
    console.print("🤖 Android Music Player Access Setup", style="bold blue")
    console.print("═" * 40)
    
    console.print("\n📱 This will help you make your music accessible to Android music players.")
    console.print("   Files downloaded to shared storage paths like /sdcard/ are accessible to other apps.")
    
    playlists = sync.list_playlists()
    if not playlists:
        console.print("\n📭 No playlists configured. Add playlists first with 'scli add' or 'scli manage'.", style="yellow")
        return
    
    console.print(f"\n📋 Current playlist storage locations:")
    
    shared_paths = []
    private_paths = []
    
    for playlist in playlists:
        directory = Path(playlist['directory'])
        
        # Check if using shared storage
        termux_shared_paths = ['/storage/emulated/', '/sdcard/', '/storage/']
        is_shared = any(str(directory).startswith(path) for path in termux_shared_paths)
        
        if is_shared:
            shared_paths.append((playlist['url'], str(directory)))
            console.print(f"  ✅ Accessible to music apps:", style="green")
            console.print(f"     {playlist['url'][:45]}...")
            console.print(f"     📁 {directory}", style="dim")
        else:
            private_paths.append((playlist['url'], str(directory)))
            console.print(f"  🔒 Private storage (not accessible to music apps):", style="yellow")
            console.print(f"     {playlist['url'][:45]}...")
            console.print(f"     📁 {directory}", style="dim")
    
    if private_paths:
        console.print(f"\n💡 To make music accessible to Android music players:", style="blue")
        console.print(f"   • Use 'scli manage' to change directories for private storage playlists")
        console.print(f"   • Recommended shared storage path: /sdcard/Music/scdl-cli/")
        console.print(f"   • Files will be directly accessible to music players")
        console.print(f"   • If you get file locking errors, use 'scli clean' and retry")
    
    if shared_paths:
        console.print(f"\n🎵 Music accessible to Android apps:", style="green")
        for url, path in shared_paths:
            console.print(f"   📁 {path}")
        
        console.print(f"\n💡 Your music players should be able to find files in these locations.")


@main.command()
@click.pass_context
def test_client_id(ctx: click.Context) -> None:
    """Test client ID auto-generation functionality."""
    from .utils.client_id import ClientIDManager
    
    config = ctx.obj['config']
    client_manager = ClientIDManager()
    
    console.print("🔍 Testing client ID functionality...", style="blue")
    
    # Test getting client ID (with auto-generation)
    with console.status("Getting client ID..."):
        client_id = config.get_client_id()
    
    if client_id:
        console.print(f"✅ Successfully obtained client ID: {client_id[:8]}...", style="green")
        
        # Test validation
        with console.status("Validating client ID..."):
            is_valid = client_manager._is_valid_client_id(client_id)
        
        if is_valid:
            console.print("✅ Client ID is valid and working", style="green")
        else:
            console.print("❌ Client ID validation failed", style="red")
    else:
        console.print("❌ Failed to obtain client ID", style="red")
        console.print("💡 Try setting a manual client ID with: scdl-cli config --client-id YOUR_ID", style="yellow")


if __name__ == '__main__':
    main()
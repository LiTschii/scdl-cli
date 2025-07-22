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
@click.pass_context
def sync(ctx: click.Context, playlist: Optional[str], dry_run: bool) -> None:
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
@click.option('--format', default='mp3', help='Default audio format')
@click.option('--quality', default='best', help='Default audio quality')
@click.option('--sync-remove-deleted/--no-sync-remove-deleted', default=True, 
              help='Remove local tracks no longer in playlist during sync')
@click.option('--sync-update-metadata/--no-sync-update-metadata', default=False,
              help='Force metadata updates during sync')
@click.option('--sync-original-art/--no-sync-original-art', default=True,
              help='Download original artwork during sync')
@click.option('--sync-original-name/--no-sync-original-name', default=True,
              help='Keep original file names during sync')
@click.pass_context
def config(
    ctx: click.Context,
    client_id: Optional[str],
    format: str,
    quality: str,
    sync_remove_deleted: bool,
    sync_update_metadata: bool,
    sync_original_art: bool,
    sync_original_name: bool
) -> None:
    """Configure scdl-cli settings."""
    config_mgr = ctx.obj['config']
    
    if client_id is None:
        console.print("📋 Client ID is optional - scdl-cli can auto-generate one if needed", style="blue")
        client_id = click.prompt('SoundCloud Client ID (press Enter to skip)', 
                               default='', show_default=False, type=str)
    
    config_data = {
        'format': format,
        'quality': quality,
        'sync': {
            'remove_deleted': sync_remove_deleted,
            'update_metadata': sync_update_metadata,
            'original_art': sync_original_art,
            'original_name': sync_original_name
        }
    }
    
    # Only set client_id if provided
    if client_id:
        # Test the provided client ID
        from .utils.client_id import ClientIDManager
        test_manager = ClientIDManager()
        if test_manager._is_valid_client_id(client_id):
            config_data['client_id'] = client_id
            console.print(f"✅ Using provided client ID: {client_id[:8]}...", style="green")
        else:
            console.print(f"❌ Provided client ID is invalid", style="red")
            console.print("✅ Will auto-generate client ID when needed", style="green")
    else:
        console.print("✅ Will auto-generate client ID when needed", style="green")
    
    config_mgr.update(config_data)
    config_mgr.save()
    
    console.print("✅ Configuration saved successfully", style="green")
    
    # Test the final configuration
    console.print("🔍 Testing client ID configuration...", style="blue")
    final_client_id = config_mgr.get_client_id()
    if final_client_id:
        console.print(f"✅ Client ID ready: {final_client_id[:8]}...", style="green")
    else:
        console.print("❌ Unable to obtain client ID", style="red")


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
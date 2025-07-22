# scdl-cli

Playlist synchronization tool for SoundCloud downloads using scdl. Keep your local music directories in sync with SoundCloud playlists.

<!-- Test comment added to test DesktopCommander MCP git workflow -->

## Features

- 🎵 **Playlist Sync**: Map SoundCloud playlists to local directories
- 🔄 **One-Command Sync**: Update all configured playlists with a single command
- 📁 **Directory Management**: Automatic directory creation and organization  
- ⚙️ **Configuration**: Simple TOML-based configuration
- 🎨 **Rich CLI**: Beautiful terminal interface with progress indicators
- ✅ **Validation**: URL and path validation with helpful error messages

## Installation

### Prerequisites

1. **Python 3.8+** is required
2. **FFmpeg** must be installed for audio processing
3. **scdl** must be installed: `pip install scdl`

### Install scdl-cli

```bash
# From source
git clone https://github.com/scdl-org/scdl-cli.git
cd scdl-cli
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

## Quick Start

### 1. Configure scdl-cli (Optional)

```bash
scdl-cli config
# Client ID is optional - will auto-generate if not provided
# Press Enter to skip manual configuration
```

### 2. Add a playlist mapping

```bash
scdl-cli add https://soundcloud.com/artist/sets/playlist-name ~/Music/MyPlaylist
```

### 3. Sync all playlists

```bash
scdl-cli sync
```

That's it! Your playlists will be kept in sync with their local directories.

## Commands

### `add <playlist_url> <directory>`

Add a playlist-directory mapping:

```bash
# Add a playlist to sync to ~/Music/ChillBeats
scdl-cli add https://soundcloud.com/user/sets/chill-beats ~/Music/ChillBeats

# Use relative paths
scdl-cli add https://soundcloud.com/user/sets/workout ./music/workout
```

### `remove <playlist_url>`

Remove a playlist from synchronization:

```bash
scdl-cli remove https://soundcloud.com/user/sets/old-playlist
```

### `list`

Show all configured playlist mappings:

```bash
scdl-cli list
```

Example output:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Playlist URL                         ┃ Directory                      ┃ Last Sync          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ soundcloud.com/user/sets/chill      │ /home/user/Music/Chill         │ 2024-01-15 14:30   │
│ soundcloud.com/user/sets/workout    │ /home/user/Music/Workout       │ Never              │
└──────────────────────────────────────┴────────────────────────────────┴────────────────────┘
```

### `sync`

Synchronize all configured playlists:

```bash
# Sync all playlists
scdl-cli sync

# Sync a specific playlist only
scdl-cli sync --playlist https://soundcloud.com/user/sets/playlist

# Dry run - see what would be downloaded without downloading
scdl-cli sync --dry-run
```

### `config`

Configure scdl-cli settings:

```bash
# Interactive configuration (client ID optional)
scdl-cli config

# Set specific options
scdl-cli config --client-id YOUR_CLIENT_ID --format mp3 --quality best

# Skip client ID (will auto-generate when needed)
scdl-cli config --format mp3 --quality best
```

### `show-config`

Display current configuration:

```bash
scdl-cli show-config
```

### `test-client-id`

Test client ID auto-generation:

```bash
scdl-cli test-client-id
```

## Configuration

scdl-cli stores configuration in `~/.config/scdl-cli/`:

- `config.toml` - General settings
- `playlists.json` - Playlist-directory mappings  
- `client_id_cache.json` - Cached auto-generated client ID

### Configuration File Example

**config.toml:**
```toml
format = "mp3"
quality = "best"
client_id = "your_soundcloud_client_id"  # Optional - will auto-generate if empty
timeout = 3600
verbose = false
```

### Environment Variables

Override config with environment variables:

- `SCDL_CLIENT_ID`
- `SCDL_FORMAT`
- `SCDL_QUALITY`
- `SCDL_VERBOSE`

## Getting a SoundCloud Client ID

To use scdl-cli, you need a SoundCloud client ID:

1. Go to [SoundCloud Developers](https://developers.soundcloud.com/)
2. Create a new app
3. Copy the Client ID
4. Configure: `scdl-cli config --client-id YOUR_CLIENT_ID`

## Workflow Example

```bash
# 1. Set up configuration
scdl-cli config --client-id abc123def456

# 2. Add your favorite playlists
scdl-cli add https://soundcloud.com/user/sets/study-music ~/Music/Study
scdl-cli add https://soundcloud.com/user/sets/workout-beats ~/Music/Workout
scdl-cli add https://soundcloud.com/user/sets/chill-vibes ~/Music/Chill

# 3. See what you've configured
scdl-cli list

# 4. Sync all playlists (run this regularly)
scdl-cli sync

# 5. Set up a cron job for automatic sync
# Add to crontab: 0 */6 * * * /usr/local/bin/scdl-cli sync
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run formatting
black src/

# Run type checking  
mypy src/

# Run tests
pytest
```

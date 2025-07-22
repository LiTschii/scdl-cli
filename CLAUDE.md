# Claude Code Instructions

This file contains important instructions and context for working with this repository.

## SCDL Research and Documentation

When working with scdl (SoundCloud Downloader) functionality:

### Always use Context7 for scdl documentation
- Use the `mcp__context7__resolve-library-id` tool to find scdl library information
- Use the `mcp__context7__get-library-docs` tool to get up-to-date scdl documentation
- This ensures you have the latest API information and usage patterns

### Use Perplexity for additional scdl research
- Use the `mcp__perplexity-ask__perplexity_ask` tool for broader research about scdl usage
- Ask about best practices, common issues, and implementation examples
- Get current information about scdl features and limitations

### SCDL Repository
- Official GitHub repository: https://github.com/scdl-org/scdl
- Always reference this repository for the most current information
- Check issues and documentation for troubleshooting

### Research Workflow
1. First use Context7 to get official scdl documentation
2. Then use Perplexity to research usage patterns and best practices
3. Reference the GitHub repository for latest updates and issues
4. Apply findings to the scdl-cli wrapper implementation

## Git Automation Script

This repository includes a git automation script (`git-commit.sh`) that simplifies the git workflow when working with Claude Code.

### Usage

```bash
# Basic commit (stages all changes and commits with message)
./git-commit.sh "commit message"

# Commit and push to remote
./git-commit.sh "commit message" --push
```

### What the script does

1. **Always runs `git add .`** to stage all changes before committing
2. **Creates commit** with the provided message
3. **Adds Claude attribution** to commit messages automatically
4. **Optionally pushes** to remote when `--push` flag is used
5. **Includes safety checks** and colored output for better UX

### Examples

```bash
# Stage, commit with message
./git-commit.sh "Fix playlist synchronization bug"

# Stage, commit, and push
./git-commit.sh "Add new sync command feature" --push

# Multi-word messages (use quotes)
./git-commit.sh "Update README with installation instructions" --push
```

### When to use

Use this script when Claude Code's bash commands are having issues or when you want a simple way to commit changes with proper attribution.

The script handles all the git workflow steps that Claude Code sometimes struggles with due to bash execution issues.

### Features

- ✅ Automatic staging of all changes
- ✅ Custom commit messages
- ✅ Optional push functionality
- ✅ Claude attribution in commits
- ✅ Error handling and validation
- ✅ Colored output for better visibility
- ✅ Safety checks (git repo, changes exist, remote configured)
#!/bin/bash

# Git commit automation script
# Usage: ./git-commit.sh "commit message" [--push]
# Example: ./git-commit.sh "Fix playlist sync bug" --push

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository!"
    exit 1
fi

# Parse arguments
COMMIT_MESSAGE=""
SHOULD_PUSH=false

# Check if at least one argument is provided
if [ $# -eq 0 ]; then
    print_error "Usage: $0 \"commit message\" [--push]"
    print_error "Example: $0 \"Add new feature\" --push"
    exit 1
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            SHOULD_PUSH=true
            shift
            ;;
        *)
            if [ -z "$COMMIT_MESSAGE" ]; then
                COMMIT_MESSAGE="$1"
            else
                print_error "Multiple commit messages provided. Use quotes for multi-word messages."
                exit 1
            fi
            shift
            ;;
    esac
done

# Check if commit message is provided
if [ -z "$COMMIT_MESSAGE" ]; then
    print_error "Commit message is required!"
    print_error "Usage: $0 \"commit message\" [--push]"
    exit 1
fi

print_status "Starting git automation..."

# Check if there are any changes to commit
if git diff --quiet && git diff --cached --quiet; then
    print_warning "No changes detected to commit."
    exit 0
fi

# Stage all changes
print_status "Staging all changes (git add .)..."
if git add .; then
    print_success "Successfully staged all changes"
else
    print_error "Failed to stage changes"
    exit 1
fi

# Show what will be committed
print_status "Changes to be committed:"
git diff --cached --name-status

# Create commit with the provided message and Claude attribution
FULL_COMMIT_MESSAGE="${COMMIT_MESSAGE}

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"

print_status "Creating commit with message: \"$COMMIT_MESSAGE\""
if git commit -m "$FULL_COMMIT_MESSAGE"; then
    print_success "Successfully created commit"
else
    print_error "Failed to create commit"
    exit 1
fi

# Push if --push flag was provided
if [ "$SHOULD_PUSH" = true ]; then
    print_status "Pushing changes to remote repository..."
    
    # Check if we have a remote configured
    if ! git remote get-url origin > /dev/null 2>&1; then
        print_error "No remote 'origin' configured. Cannot push."
        exit 1
    fi
    
    # Get current branch name
    CURRENT_BRANCH=$(git branch --show-current)
    
    # Push changes
    if git push origin "$CURRENT_BRANCH"; then
        print_success "Successfully pushed changes to origin/$CURRENT_BRANCH"
    else
        print_error "Failed to push changes"
        print_warning "Commit was created locally but not pushed"
        exit 1
    fi
fi

print_success "Git automation completed successfully!"

# Show final status
print_status "Final repository status:"
git status --short
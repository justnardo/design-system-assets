#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Installing design-system-assets skill..."

# Ensure the Claude skills directory exists
SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$SKILLS_DIR"

# Define the target directory for this skill
TARGET_DIR="$SKILLS_DIR/design-system-assets"

# Remove the existing installation if it exists
if [ -d "$TARGET_DIR" ]; then
    echo "Found existing installation at $TARGET_DIR. Removing..."
    rm -rf "$TARGET_DIR"
fi

# Copy the repository contents to the target directory
echo "Copying files to $TARGET_DIR..."
cp -r . "$TARGET_DIR"

# Clean up any git or local cache files from the installed copy
rm -rf "$TARGET_DIR/.git" 2>/dev/null || true
rm -rf "$TARGET_DIR/__pycache__" 2>/dev/null || true

echo ""
echo "Installation complete!"
echo "Restart Claude Code to pick up the new skill."

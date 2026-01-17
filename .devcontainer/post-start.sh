#!/bin/bash
# Post-start script for Codespaces - runs on EVERY container start/restart
# This ensures the venv is ready without reinstalling everything

VENV_PATH="/workspaces/green_bier_sports_ncaam_model/.venv"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  NCAAM Model - Codespaces Startup                         ║"
echo "╚════════════════════════════════════════════════════════════╝"

# Check if venv exists and is valid
if [ -f "$VENV_PATH/bin/activate" ]; then
    echo "✓ Virtual environment found"

    # Verify Python in venv works
    if "$VENV_PATH/bin/python" --version > /dev/null 2>&1; then
        echo "✓ Python venv is healthy"
    else
        echo "⚠ Venv Python broken, recreating..."
        python -m venv "$VENV_PATH" --clear
        source "$VENV_PATH/bin/activate"
        pip install --upgrade pip -q
        pip install -r requirements-dev.txt -q || true
        pip install -r services/prediction-service-python/requirements.txt -q || true
    fi
else
    echo "⚠ Virtual environment not found, creating..."
    python -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    pip install --upgrade pip -q
    pip install -r requirements-dev.txt -q || true
    pip install -r services/prediction-service-python/requirements.txt -q || true
fi

# Add auto-activation to .bashrc if not already present
BASHRC="$HOME/.bashrc"
ACTIVATION_LINE='[ -f "/workspaces/green_bier_sports_ncaam_model/.venv/bin/activate" ] && source "/workspaces/green_bier_sports_ncaam_model/.venv/bin/activate"'

# Create .bashrc if it doesn't exist
touch "$BASHRC"

if ! grep -qF ".venv/bin/activate" "$BASHRC" 2>/dev/null; then
    echo "" >> "$BASHRC"
    echo "# Auto-activate NCAAM Model venv" >> "$BASHRC"
    echo "$ACTIVATION_LINE" >> "$BASHRC"
    echo "✓ Added venv auto-activation to .bashrc"
fi

echo ""
echo "Ready! Virtual environment will auto-activate in new terminals."
echo "Run 'source .venv/bin/activate' in existing terminals."
echo ""

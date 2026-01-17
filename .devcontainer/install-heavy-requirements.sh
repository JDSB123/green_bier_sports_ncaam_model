#!/bin/bash
set -e
echo "Installing heavy Python dependencies (this may take a while)..."
pip install --cache-dir /home/codespace/.cache/pip --prefer-binary -r services/prediction-service-python/requirements-heavy.txt
echo "Heavy dependencies installed."

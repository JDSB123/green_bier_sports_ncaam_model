# Devcontainer Configuration

This project includes two devcontainer configurations:

## Current Setup (Local Build)

**File**: `devcontainer.json`
- Builds the container image locally from `Dockerfile`
- Slower initial startup (~5-10 minutes)
- Good for testing devcontainer changes
- Uses `INSTALL_HEAVY=false` by default

## Pre-built Image (Faster)

**File**: `devcontainer.prebuilt.json`
- Uses pre-built image from GitHub Container Registry
- Much faster startup (~30-60 seconds)
- Automatically updated on push to main branch
- Requires successful GitHub Actions workflow run

### Switching to Pre-built Image

1. Wait for the GitHub Actions workflow to complete: https://github.com/JDSB123/green_bier_sports_ncaam_model/actions/workflows/build-devcontainer-image.yml

2. Replace `devcontainer.json` with `devcontainer.prebuilt.json`:
   ```bash
   cp .devcontainer/devcontainer.prebuilt.json .devcontainer/devcontainer.json
   ```

3. Rebuild the devcontainer:
   - Press `F1` → `Dev Containers: Rebuild Container`

### Available Images

- `ghcr.io/jdsb123/green_bier_sports_ncaam_model-devcontainer:latest` - Standard (lighter)
- `ghcr.io/jdsb123/green_bier_sports_ncaam_model-devcontainer:latest-heavy` - With heavy ML dependencies

To use the heavy variant, change the `image` line in `devcontainer.prebuilt.json` to:
```json
"image": "ghcr.io/jdsb123/green_bier_sports_ncaam_model-devcontainer:latest-heavy",
```

## Workflow

The devcontainer image is automatically rebuilt when:
- Changes are pushed to the `main` branch
- Manual trigger via GitHub Actions UI

The workflow builds both standard and heavy variants in parallel.

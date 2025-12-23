# Cleanup script for stale Docker images and containers
# Usage: .\scripts\cleanup_docker.ps1

Write-Host "Cleaning up stale Docker resources..." -ForegroundColor Cyan

# 1. Remove containers associated with old project names or versions
$containers = docker ps -a --filter "name=ncaam" --format "{{.ID}} {{.Names}}"
if ($containers) {
    Write-Host "Found containers to check:"
    $containers | ForEach-Object { Write-Host "  $_" }
    
    # Ask for confirmation or just do it if they are stopped? 
    # For safety, we'll just list them and suggest removal command
    Write-Host "To remove all stopped containers: docker container prune -f" -ForegroundColor Yellow
}

# 2. Remove images from the old ACR (ncaamgbsvacr)
$oldImages = docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -like "*ncaamgbsvacr*" }
if ($oldImages) {
    Write-Host "Found images from old ACR (ncaamgbsvacr):" -ForegroundColor Yellow
    $oldImages | ForEach-Object { Write-Host "  $_" }
    
    Write-Host "Removing old ACR images..." -ForegroundColor Cyan
    $oldImages | ForEach-Object { 
        docker rmi $_ 
        Write-Host "  Removed $_" -ForegroundColor Green
    }
} else {
    Write-Host "No images from old ACR (ncaamgbsvacr) found." -ForegroundColor Green
}

# 3. Remove dangling images
Write-Host "Pruning dangling images..." -ForegroundColor Cyan
docker image prune -f

Write-Host "Cleanup complete." -ForegroundColor Green

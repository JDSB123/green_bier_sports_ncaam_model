# Check R installation and configuration
Write-Host "=== R Setup Verification ===" -ForegroundColor Cyan

$rPath = where.exe R 2>$null
if ($rPath) {
    Write-Host "✓ R is installed at: $rPath" -ForegroundColor Green
    
    # Check R version
    $version = & R --version 2>$null | Select-Object -First 1
    Write-Host "  $version" -ForegroundColor Green
} else {
    Write-Host "✗ R is NOT installed" -ForegroundColor Red
    Write-Host "  Download from: https://cran.r-project.org/" -ForegroundColor Yellow
}

# Check VS Code R extension
Write-Host "`n=== VS Code R Extension ===" -ForegroundColor Cyan
$ext = code --list-extensions 2>$null | Select-String "REditorSupport.r"
if ($ext) {
    Write-Host "✓ R Language Support is installed" -ForegroundColor Green
} else {
    Write-Host "✗ R Language Support extension not found" -ForegroundColor Red
}

Write-Host "`n=== Workspace Settings ===" -ForegroundColor Cyan
if (Test-Path ".\.vscode\settings.json") {
    Write-Host "✓ Workspace settings configured" -ForegroundColor Green
} else {
    Write-Host "✗ Workspace settings not found" -ForegroundColor Red
}

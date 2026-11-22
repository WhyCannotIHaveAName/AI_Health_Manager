param([string]$Python = "python")
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $Python -m tests.gui_smoke
if ($LASTEXITCODE -ne 0) { throw 'GUI smoke test failed' }
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name AIHealthManager --collect-all customtkinter --additional-hooks-dir scripts/hooks --add-data 'data;data' run.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
# Always exercise the frozen executable, not only the source interpreter.
# The network probe sends a synthetic invalid key, never the saved user key.
Start-Process -FilePath (Join-Path (Get-Location) 'dist\AIHealthManager\AIHealthManager.exe') -ArgumentList '--diagnose' -WindowStyle Hidden -Wait
$diagnostic = Get-Content -Raw -LiteralPath 'dist\AIHealthManager\diagnostics.json' | ConvertFrom-Json
foreach ($check in 'tls_context', 'proxy_discovery', 'key_storage') {
    if (-not $diagnostic.checks.$check.ok) { throw "Frozen application check failed: $check" }
}
if (-not $diagnostic.checks.api_transport.ok) { Write-Warning 'API transport probe did not receive the expected HTTP 401; check diagnostics.json and network connectivity.' }
Write-Output 'Built dist\AIHealthManager\AIHealthManager.exe'

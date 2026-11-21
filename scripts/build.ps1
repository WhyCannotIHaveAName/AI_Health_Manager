param([string]$Python = "python")
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $Python -m tests.gui_smoke
if ($LASTEXITCODE -ne 0) { throw 'GUI smoke test failed' }
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name AIHealthManager --collect-all customtkinter --add-data 'data;data' run.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Output 'Built dist\AIHealthManager\AIHealthManager.exe'

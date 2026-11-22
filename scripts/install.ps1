param(
    [string]$Source = (Join-Path (Split-Path $PSScriptRoot -Parent) 'dist\AIHealthManager'),
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\AIHealthManager'),
    [switch]$Portable
)
$ErrorActionPreference = 'Stop'
$Source = [IO.Path]::GetFullPath($Source)
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
if (-not (Test-Path -LiteralPath (Join-Path $Source 'AIHealthManager.exe'))) { throw 'Build the application first.' }
if ($InstallDir.TrimEnd('\') -eq [IO.Path]::GetPathRoot($InstallDir)) { throw 'Choose an application folder, not a drive root.' }
if ($InstallDir -eq $Source) { throw 'Install directory must differ from build directory.' }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
# Never remove the target or userdata when updating an installation.
Get-ChildItem -LiteralPath $Source | Copy-Item -Destination $InstallDir -Recurse -Force
if ($Portable) { Set-Content -LiteralPath (Join-Path $InstallDir 'portable.flag') -Value 'Store data next to this application.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $InstallDir 'AI Health Manager.lnk'))
$shortcut.TargetPath = Join-Path $InstallDir 'AIHealthManager.exe'
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()
Write-Output "Installed: $InstallDir\AIHealthManager.exe"

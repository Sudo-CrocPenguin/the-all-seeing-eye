param(
    [string]$InstallDir = "C:\Program Files\TheAllSeeingEye"
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Este desinstalador debe ejecutarse como administrador."
}

$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
Stop-Service -Name "AllSeeingEyeAgent" -ErrorAction SilentlyContinue
& $python -m agent.app.windows_service remove

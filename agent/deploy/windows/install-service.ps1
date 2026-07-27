param(
    [string]$InstallDir = "C:\Program Files\TheAllSeeingEye",
    [string]$ConfigDir = "$env:ProgramData\TheAllSeeingEye",
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$DeviceId = "",
    [string]$AgentToken = "",
    [int]$HeartbeatIntervalSeconds = 60,
    [int]$ScanIntervalSeconds = 15
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Este instalador debe ejecutarse como administrador."
}

$sourceDir = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

Get-ChildItem -Path $sourceDir -Force |
    Where-Object { $_.Name -notin @(".git", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache") } |
    Copy-Item -Destination $InstallDir -Recurse -Force

$python = Join-Path $InstallDir ".venv\Scripts\python.exe"
py -3 -m venv (Join-Path $InstallDir ".venv")
& $python -m pip install --upgrade pip
& $python -m pip install -e "$InstallDir[windows-service]"

$envFile = Join-Path $ConfigDir "agent.env"
@(
    "AGENT_BACKEND_URL=$BackendUrl",
    "AGENT_DEVICE_ID=$DeviceId",
    "AGENT_TOKEN=$AgentToken",
    "AGENT_TOKEN_HEADER=X-Agent-Token",
    "AGENT_HEARTBEAT_INTERVAL_SECONDS=$HeartbeatIntervalSeconds",
    "AGENT_SCAN_INTERVAL_SECONDS=$ScanIntervalSeconds",
    "AGENT_NETWORK_EVENT_DEDUP_SECONDS=300",
    "AGENT_REQUEST_TIMEOUT_SECONDS=10"
) | Set-Content -Path $envFile -Encoding UTF8

& $python -m agent.app.windows_service install --startup auto
& $python -m agent.app.windows_service start
Get-Service -Name "AllSeeingEyeAgent"

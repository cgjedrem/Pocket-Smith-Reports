# Run the Pocket-Smith Reports FastAPI dev server via uv.
# uv manages the venv + runs uvicorn. .pth file handles PYTHONPATH.
# Usage: .\scripts\run_api.ps1
# Prereq: uv installed (https://docs.astral.sh/uv/)
param(
    [string]$Host_ = "127.0.0.1",
    [int]$Port = 8000
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    # Find uv — check PATH, then default install location.
    $uvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if (-not $uvExe) {
        $uvExe = "$env:USERPROFILE\.local\bin\uv.exe"
    }
    if (-not (Test-Path $uvExe)) {
        throw "uv not found. Install: irm https://astral.sh/uv/install.ps1 | iex"
    }
    & $uvExe run python -m uvicorn budget_api.main:app --host $Host_ --port $Port
}
finally {
    Pop-Location
}
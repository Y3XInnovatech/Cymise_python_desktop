Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot/.."
Push-Location $repoRoot
try {
    python -m ruff check src tests
    python -m black --check src tests
}
finally {
    Pop-Location
}

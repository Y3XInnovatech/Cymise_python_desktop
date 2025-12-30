Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot/.."
Push-Location $repoRoot
try {
    python -m ruff check --fix src tests
    python -m black src tests
}
finally {
    Pop-Location
}

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot/.."
Push-Location $repoRoot
try {
    python -m pytest
}
finally {
    Pop-Location
}

$ErrorActionPreference='Stop'
$Target=Join-Path (Split-Path -Parent $PSScriptRoot) 'start_workbench.ps1'
if (-not (Test-Path $Target)) { throw "Missing parent script: $Target" }
& $Target @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $Root
try {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is required' }
  docker compose up -d postgres
  if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed' }
  $ready=$false
  for($i=0;$i -lt 40;$i++) { docker compose exec -T postgres pg_isready -U lab -d industrial_lab *> $null; if($LASTEXITCODE -eq 0){$ready=$true;break};Start-Sleep -Seconds 2 }
  if (-not $ready) { throw 'PostgreSQL did not become ready' }
  # Create-only, never drop or overwrite the existing demo database.
  $exists = docker compose exec -T postgres psql -U lab -d postgres -Atc "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname='industrial_lab_demo') THEN 1 ELSE 0 END"
  if ($LASTEXITCODE -ne 0) { throw "Demo database existence check failed" }
  if ($exists -ne '1') {
    docker compose exec -T postgres psql -U lab -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE industrial_lab_demo'
    if ($LASTEXITCODE -ne 0) { throw 'Demo database creation failed' }
  }
  $Migrations=@('schema.sql','003_v03.sql','004_snapshot_fence.sql','005_effective_bom.sql','006_m2_integration.sql','007_normalized_pegging.sql','008_workflow_runtime.sql','009_workflow_worker.sql','010_agent_harness.sql','011_agent_governance.sql','012_outbox_receipts.sql')
  foreach($name in $Migrations) {
    docker compose cp (Join-Path $Root "database\$name") "postgres:/tmp/$name"
    if ($LASTEXITCODE -ne 0) { throw "Copy failed: $name" }
    docker compose exec -T postgres psql -U lab -d industrial_lab_demo -v ON_ERROR_STOP=1 -f "/tmp/$name"
    if ($LASTEXITCODE -ne 0) { throw "Migration failed: $name" }
  }
  $Python=Join-Path $Root 'backend\.venv314\Scripts\python.exe'
  if (-not (Test-Path $Python)) { throw 'Run .\run_pg16_gate.ps1 to create Python 3.14 venv first' }
  $env:DATABASE_URL='postgresql://lab:local_demo_only@localhost:5432/industrial_lab_demo'
  Push-Location (Join-Path $Root 'backend')
  try { & $Python -m scripts.seed_workbench_demo; if($LASTEXITCODE -ne 0){throw 'Demo seed failed'} }
  finally { Pop-Location }
  Write-Host 'Demo database ready. Run .\start_workbench.ps1' -ForegroundColor Green
} finally { Pop-Location }

$ErrorActionPreference = 'Stop'
$container = 'm2_pg16_gate-postgres-1'
$db = 'industrial_lab_v14_test'
if (-not (Test-Path '.\backend\tests\test_srm_v14_pg16.py')) { throw 'STOP: run from m2_pg16_gate' }
$running = docker inspect --format '{{.State.Running}}' $container 2>$null
if ($LASTEXITCODE -ne 0 -or $running -ne 'true') { throw 'STOP: PG16 container not running' }
$exists = docker exec $container psql -X -U lab -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$db';"
if ($LASTEXITCODE -ne 0 -or $exists -ne '1') { throw 'STOP: isolated v14 test DB missing' }
$count = docker exec $container psql -X -U lab -d $db -Atc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='srm_v14' AND table_type='BASE TABLE';"
if ($LASTEXITCODE -ne 0 -or $count -ne '10') { throw "STOP: srm_v14 schema incomplete (tables=$count)" }
$raw = docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' $container | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' } | Select-Object -First 1
if (-not $raw) { throw 'STOP: Docker password unavailable' }
$encoded = [uri]::EscapeDataString($raw.Substring('POSTGRES_PASSWORD='.Length))
$env:TEST_DATABASE_URL = "postgresql://lab:${encoded}@127.0.0.1:5432/$db"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
Remove-Variable raw,encoded
if (([uri]$env:TEST_DATABASE_URL).AbsolutePath.TrimStart('/') -ne $db) { throw 'STOP: unexpected DB' }
$env:PUBLIC_READ_ONLY = '0'
Push-Location '.\backend'
try {
  Write-Host 'TARGET: industrial_lab_v14_test'
  py -3.14 -m pytest tests/test_srm_v14_batch_a.py tests/test_srm_v14_readonly.py tests/test_srm_v14_pg16.py -v -s -rs
  if ($LASTEXITCODE -ne 0) { throw 'RC2 TEST FAILED' }
  Write-Host 'RC2 TEST COMMAND PASSED — verify 6 passed, 0 skipped in pytest summary'
} finally { Pop-Location }

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$image = 'industrial-ai-paas-v18:c43-repaired-20261101'
$name = 'industrial-ai-paas-v18-c43-repaired'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'DOCKER_NOT_FOUND' }
$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $name }
if ($existing) { throw "C43_CONTAINER_ALREADY_EXISTS: $name (preserve; do not overwrite)" }

Write-Host '=== C4.3 FRESH IMAGE BUILD ===' -ForegroundColor Cyan
docker build --no-cache -t $image $root
if ($LASTEXITCODE -ne 0) { throw 'C43_DOCKER_BUILD_FAILED' }

$meta = docker image inspect $image | ConvertFrom-Json
$info = $meta[0]
if ($info.Config.User -ne '10001:10001') { throw "IMAGE_USER_FAILED: $($info.Config.User)" }
if ($info.Config.Labels.'org.opencontainers.image.version' -ne '1.8-c4.3') { throw 'IMAGE_LABEL_FAILED' }
$imageEnv = @($info.Config.Env)
if ($imageEnv -notcontains 'PUBLIC_READ_ONLY=1') { throw 'IMAGE_PUBLIC_READ_ONLY_FAILED' }
if ($imageEnv -notcontains 'DEMO_WRITE_ENABLED=0') { throw 'IMAGE_DEMO_WRITE_FAILED' }

Write-Host '=== C4.3 ISOLATED CONTAINER CREATE ===' -ForegroundColor Cyan
docker create `
    --name $name `
    --user '10001:10001' `
    --read-only `
    --cap-drop ALL `
    --security-opt no-new-privileges:true `
    --network none `
    --pids-limit 128 `
    --memory 512m `
    --cpus 1 `
    --tmpfs /tmp:rw,noexec,nosuid,size=64m `
    -e 'PUBLIC_READ_ONLY=1' `
    -e 'DEMO_WRITE_ENABLED=0' `
    $image
if ($LASTEXITCODE -ne 0) { throw 'C43_CONTAINER_CREATE_FAILED' }

docker start $name
if ($LASTEXITCODE -ne 0) { throw 'C43_CONTAINER_START_FAILED' }
Start-Sleep -Seconds 5

$raw = docker inspect $name
if ($LASTEXITCODE -ne 0) { throw 'C43_CONTAINER_INSPECT_FAILED' }
$c = @($raw | ConvertFrom-Json)[0]

# Runtime smoke: Python 3.14, application import and public MCP route boundary.
$runtimeCheck = docker exec $name python -c "import sys; from app.main import app; paths=set(app.openapi().get('paths',{})); assert sys.version_info[:2] == (3,14), sys.version; assert '/api/v1/portfolio/mcp/tools' in paths; assert '/api/v1/workbench/snapshot' in paths; assert '/mcp' not in paths; assert not any(p.startswith('/mcp/') for p in paths); print('PYTHON',sys.version.split()[0]); print('PUBLIC_MCP_ROUTE',False); print('PORTFOLIO_EVIDENCE_ROUTE',True); print('WORKBENCH_SNAPSHOT_ROUTE',True)"
if ($LASTEXITCODE -ne 0) { throw 'C43_RUNTIME_IMPORT_OR_ROUTE_BOUNDARY_FAILED' }
$logs = docker logs --tail 60 $name
if ($LASTEXITCODE -ne 0 -or $logs -notmatch 'Application startup complete') { throw 'C43_APPLICATION_STARTUP_FAILED' }
$processes = docker top $name
if ($LASTEXITCODE -ne 0 -or $processes -notmatch 'uvicorn') { throw 'C43_UVICORN_PROCESS_FAILED' }
$checks = [ordered]@{
    NonRoot = ($c.Config.User -eq '10001:10001')
    ReadOnlyRootFS = ($c.HostConfig.ReadonlyRootfs -eq $true)
    CapDropAll = ($c.HostConfig.CapDrop -contains 'ALL')
    NoNewPrivileges = ($c.HostConfig.SecurityOpt -contains 'no-new-privileges:true')
    NetworkIsolated = ($c.HostConfig.NetworkMode -eq 'none')
    PidsLimited = ($c.HostConfig.PidsLimit -eq 128)
    MemoryLimited = ($c.HostConfig.Memory -eq 536870912)
    CPURestricted = ($c.HostConfig.NanoCpus -eq 1000000000)
    PublicReadOnly = ($c.Config.Env -contains 'PUBLIC_READ_ONLY=1')
    DemoWriteDisabled = ($c.Config.Env -contains 'DEMO_WRITE_ENABLED=0')
    Running = ($c.State.Running -eq $true)
}
$checks.GetEnumerator() | ForEach-Object {
    $status = if ($_.Value) { 'PASS' } else { 'FAIL' }
    $color = if ($_.Value) { 'Green' } else { 'Red' }
    Write-Host "$($_.Key): $status" -ForegroundColor $color
}
if (@($checks.GetEnumerator() | Where-Object { -not $_.Value }).Count -gt 0) {
    throw 'C43_RUNTIME_SECURITY_FAILED'
}

Write-Host "IMAGE_ID=$($info.Id)" -ForegroundColor Cyan
Write-Host "CONTAINER=$name" -ForegroundColor Cyan
Write-Host 'C43_DOCKER_SECURITY_GATE: PASS' -ForegroundColor Green
Write-Host 'Container is intentionally preserved and has no external network or published ports.'

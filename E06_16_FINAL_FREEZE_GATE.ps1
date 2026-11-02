[CmdletBinding()]
param([string]$ProjectRoot = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$Backend = Join-Path $ProjectRoot 'backend'
if (-not (Test-Path (Join-Path $Backend 'pyproject.toml'))) {
    throw 'PROJECT_ROOT_INVALID: backend/pyproject.toml not found.'
}

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Evidence = Join-Path $ProjectRoot ("E06_16_FINAL_EVIDENCE_" + $Stamp)
New-Item -ItemType Directory -Path $Evidence | Out-Null
$GateStatus = 'HOLD'
$Failures = New-Object System.Collections.Generic.List[string]
$EnvNames = @(
    'DATABASE_URL','TEST_DATABASE_URL','M1_TEST_DATABASE_URL',
    'V15_BUSINESS_DATABASE_URL','E06_ALLOW_ISOLATED_DB_TESTS',
    'V18_ALLOW_ISOLATED_PG16','V18_ISOLATED_PG16_DSN'
)
$EnvBackup = @{}
foreach ($n in $EnvNames) { $EnvBackup[$n] = [Environment]::GetEnvironmentVariable($n,'Process') }

function Write-Evidence {
    param([string]$Name,[string]$Value)
    [System.IO.File]::WriteAllText((Join-Path $Evidence $Name),$Value,(New-Object System.Text.UTF8Encoding($true)))
}
function Invoke-Native {
    param([string]$Label,[string]$Executable,[string[]]$Arguments,[string]$LogName)
    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Executable @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    $lines = @($output | ForEach-Object { "$_" })
    if ($LogName) { Write-Evidence $LogName (($lines -join "`r`n") + "`r`n") }
    foreach ($line in $lines) { Write-Host $line }
    if ($code -ne 0) { throw "$Label failed (exit=$code)." }
    return ($lines -join "`n").Trim()
}
function Invoke-PsqlReadOnly {
    param([string]$Database,[string]$Sql,[string]$Label,[string]$LogName)
    $value = Invoke-Native $Label 'docker' @(
        'exec','industrial-v18-pg16-test','psql','-U','v18_tester','-d',$Database,
        '-X','-A','-t','-v','ON_ERROR_STOP=1','-c',$Sql
    ) $LogName
    return $value.Trim()
}

try {
    Write-Host 'E06-16 FINAL FREEZE GATE (READ-ONLY DATABASE MODE)' -ForegroundColor Green

    # 1. Windows PowerShell 5.1
    $psVersion = $PSVersionTable.PSVersion.ToString()
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
        throw "WINDOWS_POWERSHELL_5_1_REQUIRED: current=$psVersion"
    }
    Write-Evidence 'powershell_version.txt' "Windows PowerShell $psVersion"

    # 2. Python 3.14
    $pythonVersion = Invoke-Native 'Python 3.14 version' 'py' @('-3.14','--version') 'python_version.txt'
    if ($pythonVersion -notmatch 'Python 3\.14') { throw "PYTHON_3_14_REQUIRED: $pythonVersion" }

    # 3. Docker / PG16 identity
    $dockerVersion = Invoke-Native 'Docker server version' 'docker' @('version','--format','{{.Server.Version}}') 'docker_version.txt'
    $running = Invoke-Native 'PG16 container running state' 'docker' @('inspect','-f','{{.State.Running}}','industrial-v18-pg16-test') 'container_running.txt'
    if ($running -ne 'true') { throw 'PG16_CONTAINER_NOT_RUNNING' }
    $image = Invoke-Native 'PG16 container image' 'docker' @('inspect','-f','{{.Config.Image}}','industrial-v18-pg16-test') 'container_image.txt'
    if ($image -ne 'postgres:16') { throw "POSTGRES_16_IMAGE_REQUIRED: $image" }
    $portsRaw = Invoke-Native 'PG16 container port mapping' 'docker' @('inspect','-f','{{json .NetworkSettings.Ports}}','industrial-v18-pg16-test') 'container_ports.json'
    $ports = $portsRaw | ConvertFrom-Json
    $hostPorts = @($ports.'5432/tcp' | ForEach-Object { [int]$_.HostPort })
    if ($hostPorts -notcontains 55432) { throw 'EXPECTED_PORT_MAPPING_55432_TO_5432_NOT_FOUND' }

    # The existing acceptance database is identity-checked only. No writes are issued.
    $acceptIdentity = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_acceptance' `
      "SELECT current_database()||'|'||current_user||'|'||current_setting('server_version_num')||'|'||pg_is_in_recovery();" `
      'Existing acceptance DB identity (read-only)' 'acceptance_db_identity.txt'
    if ($acceptIdentity -notmatch '^industrial_ai_v18_e06_acceptance\|v18_tester\|16[0-9]{4}\|false$') {
        throw "ACCEPTANCE_DATABASE_IDENTITY_MISMATCH: $acceptIdentity"
    }

    $replayIdentity = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT current_database()||'|'||current_user||'|'||current_setting('server_version_num')||'|'||pg_is_in_recovery();" `
      'Replay DB identity (read-only)' 'replay_db_identity.txt'
    if ($replayIdentity -notmatch '^industrial_ai_v18_e06_migration_replay\|v18_tester\|16[0-9]{4}\|false$') {
        throw "REPLAY_DATABASE_IDENTITY_MISMATCH: $replayIdentity"
    }

    $ledger = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT count(*) FROM platform.e06_schema_migrations;" 'Replay migration ledger count' 'migration_ledger_count.txt'
    if ($ledger -ne '11') { throw "EXPECTED_11_CORE_MIGRATIONS: found=$ledger" }

    $schemas = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT count(*) FROM pg_namespace WHERE nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit');" `
      'Replay schema count' 'schema_count.txt'
    $tables = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT count(*) FROM pg_tables WHERE schemaname IN ('mock_erp','mock_wms','mock_mes','platform','audit');" `
      'Replay business table count' 'business_table_count.txt'
    $invalidIndexes = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT count(*) FROM pg_index x JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND NOT x.indisvalid;" `
      'Invalid index count' 'invalid_index_count.txt'
    $unvalidated = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND NOT c.convalidated;" `
      'Unvalidated constraint count' 'unvalidated_constraint_count.txt'
    $brokenFk = Invoke-PsqlReadOnly 'industrial_ai_v18_e06_migration_replay' `
      "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND c.contype='f' AND (c.confrelid=0 OR NOT EXISTS (SELECT 1 FROM pg_class r WHERE r.oid=c.confrelid));" `
      'Broken foreign key count' 'broken_fk_count.txt'
    if ($schemas -ne '5') { throw "EXPECTED_5_SCHEMAS: found=$schemas" }
    if ([int]$tables -lt 31) { throw "EXPECTED_AT_LEAST_31_TABLES: found=$tables" }
    if ($invalidIndexes -ne '0') { throw "INVALID_INDEXES_FOUND: $invalidIndexes" }
    if ($unvalidated -ne '0') { throw "UNVALIDATED_CONSTRAINTS_FOUND: $unvalidated" }
    if ($brokenFk -ne '0') { throw "BROKEN_FOREIGN_KEYS_FOUND: $brokenFk" }

    # 4. Source inventory verification. Runtime evidence folders are excluded.
    $inventoryPath = Join-Path $ProjectRoot 'E06_16_FILE_INVENTORY.json'
    if (-not (Test-Path $inventoryPath)) { throw 'E06_16_FILE_INVENTORY_MISSING' }
    $inventory = Get-Content -LiteralPath $inventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $inventoryFailures = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $inventory) {
        $filePath = Join-Path $ProjectRoot $entry.path
        if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
            $inventoryFailures.Add("MISSING: $($entry.path)")
            continue
        }
        $actual = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $entry.sha256) { $inventoryFailures.Add("HASH_MISMATCH: $($entry.path)") }
    }
    if ($inventoryFailures.Count -gt 0) {
        Write-Evidence 'inventory_failures.txt' ($inventoryFailures -join "`r`n")
        throw "SOURCE_INVENTORY_FAILED: $($inventoryFailures.Count) issue(s)"
    }
    Write-Evidence 'source_inventory_status.txt' "PASS: $($inventory.Count) files verified against E06_16_FILE_INVENTORY.json"

    # 5. Offline pytest only. All database DSNs and opt-in flags are withheld.
    foreach ($n in $EnvNames) { [Environment]::SetEnvironmentVariable($n,$null,'Process') }
    Push-Location $Backend
    try {
        $junit = Join-Path $Evidence 'pytest_junit.xml'
        $pytestOutput = & py -3.14 -m pytest -q -rs "--junitxml=$junit" 2>&1
        $pytestCode = $LASTEXITCODE
        $pytestLines = @($pytestOutput | ForEach-Object { "$_" })
        Write-Evidence 'pytest_full_offline.txt' ($pytestLines -join "`r`n")
        $pytestLines | ForEach-Object { Write-Host $_ }
        if ($pytestCode -ne 0) { $Failures.Add("PYTEST_EXIT_$pytestCode") }
    } finally { Pop-Location }

    # 6. Per-test skip classification from JUnit XML (not an aggregate guess).
    if (-not (Test-Path $junit)) {
        $Failures.Add('PYTEST_JUNIT_XML_MISSING')
        $skipRows = @()
        $passCount = 0; $skipCount = 0; $failureCount = 1; $errorCount = 0
    } else {
        [xml]$xml = Get-Content -LiteralPath $junit -Raw -Encoding UTF8
        $cases = @($xml.SelectNodes('//testcase'))
        $skipNodes = @($xml.SelectNodes('//testcase[skipped]'))
        $passCount = 0; $failureCount = 0; $errorCount = 0
        $skipRows = @()
        $offlineModuleNames = @(
            'test_integrated_m2','test_agent_harness_unit','test_mcp_v15_full_batch_unit',
            'test_mcp_v15_gateway_unit','test_mcp_v15_release_contract','test_mcp_v15_security_unit',
            'test_mes_v13_batch_a','test_mes_v13_batch_b_contract','test_mes_v13_batch_c_gate',
            'test_pegging','test_pegging_report_v04','test_snapshot_fence','test_srm_v14_batch_a',
            'test_srm_v14_readonly','test_w3_workbench_mrp','test_wms_v12_unit',
            'test_workbench_schema_contract','test_workbench_unit','test_workbench_v02_unit',
            'test_workflow_unit','test_workflow_v03_unit','test_workflow_worker_unit'
        )
        foreach ($case in $cases) {
            $skipElement = $case.SelectSingleNode('skipped')
            $failureElement = $case.SelectSingleNode('failure')
            $errorElement = $case.SelectSingleNode('error')
            if ($skipElement) {
                $reason = [string]$skipElement.GetAttribute('message')
                if (-not $reason) { $reason = [string]$skipElement.InnerText }
                $module = [string]$case.classname
                $node = "$module.$($case.name)"
                if ($reason -match 'E06: database tests disabled by default') {
                    $category = 'DATABASE_TEST_DISABLED_BY_DEFAULT'
                } elseif ($reason -match 'could not import|No module named|ImportError') {
                    $category = 'DEPENDENCY_MISSING_REVIEW_REQUIRED'
                } elseif ($reason -match 'not configured|required|not set|unavailable') {
                    $category = 'ENVIRONMENT_PREREQUISITE_REVIEW_REQUIRED'
                } else {
                    $category = 'MANUAL_REVIEW_REQUIRED'
                }
                if ($offlineModuleNames | Where-Object { $module -match [regex]::Escape($_) }) {
                    $category = 'FALSE_POSITIVE_OFFLINE_TEST_STILL_SKIPPED'
                }
                $skipRows += [pscustomobject]@{nodeid=$node;reason=$reason;category=$category}
            } elseif ($failureElement) {
                $failureCount++
            } elseif ($errorElement) {
                $errorCount++
            } else {
                $passCount++
            }
        }
        $skipCount = $skipRows.Count
        $skipRows | Export-Csv -LiteralPath (Join-Path $Evidence 'skip_classification.csv') -NoTypeInformation -Encoding UTF8
        $groups = $skipRows | Group-Object category | Sort-Object Name
        $md = New-Object System.Collections.Generic.List[string]
        $md.Add('# E06-16 Skip Classification')
        $md.Add('')
        $md.Add("| Category | Count |")
        $md.Add("|---|---:|")
        foreach ($g in $groups) { $md.Add("| $($g.Name) | $($g.Count) |") }
        $md.Add('')
        $md.Add("Total: $skipCount skipped test cases. Each case is listed in `skip_classification.csv`.")
        Write-Evidence 'skip_classification.md' ($md -join "`r`n")

        if (($skipRows | Where-Object { $_.category -ne 'DATABASE_TEST_DISABLED_BY_DEFAULT' }).Count -gt 0) {
            $Failures.Add('SKIP_REASONS_REQUIRE_MANUAL_REVIEW')
        }
        if (($skipRows | Where-Object { $_.category -eq 'FALSE_POSITIVE_OFFLINE_TEST_STILL_SKIPPED' }).Count -gt 0) {
            $Failures.Add('OFFLINE_TESTS_STILL_BLOCKED_BY_DB_GUARD')
        }
    }

    # 7. Summary. Database queries above are SELECT-only; no migrations or writes were run.
    if ($failureCount -gt 0 -or $errorCount -gt 0) { $Failures.Add("PYTEST_FAILURES=$failureCount; ERRORS=$errorCount") }
    if ($Failures.Count -eq 0) { $GateStatus = 'PASS' }

    $report = @"
# E06-16 Final Freeze Gate

- Status: **$GateStatus**
- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
- Windows PowerShell: $psVersion
- Python: $pythonVersion
- Docker server: $dockerVersion
- Container: industrial-v18-pg16-test / postgres:16 / host port 55432
- Acceptance DB: $acceptIdentity (identity check only)
- Replay DB: $replayIdentity
- Core migration ledger rows: $ledger
- Application schemas: $schemas
- Business tables: $tables
- Invalid indexes: $invalidIndexes
- Unvalidated constraints: $unvalidated
- Broken foreign keys: $brokenFk
- Pytest passed: $passCount
- Pytest skipped: $skipCount
- Pytest failures: $failureCount
- Pytest errors: $errorCount

## Safety boundary

- No migration was executed.
- No database write statement was issued.
- The existing acceptance database was identity-checked only.
- The replay database was queried using SELECT statements only.
- No Neon, Render, or production endpoint was accessed.
- No database, schema, table, role, or historical data was deleted.

## Gate findings

$(if ($Failures.Count -eq 0) { 'All configured checks passed.' } else { ($Failures | ForEach-Object { "- $_" }) -join "`r`n" })

## Evidence

Evidence directory: `$Evidence`

This gate does not certify browser-backed end-to-end behavior or production readiness.
"@
    Write-Evidence 'E06_16_FINAL_ACCEPTANCE_REPORT.md' $report
    Write-Evidence 'gate_status.txt' $GateStatus

    if ($GateStatus -eq 'PASS') {
        Write-Host "`nE06-16 FINAL FREEZE GATE PASS" -ForegroundColor Green
    } else {
        Write-Host "`nE06-16 FINAL FREEZE GATE HOLD" -ForegroundColor Yellow
        Write-Host ($Failures -join "`r`n")
    }
    Write-Host "Evidence: $Evidence"
    if ($GateStatus -ne 'PASS') { exit 2 }
}
catch {
    $Failures.Add($_.Exception.Message)
    Write-Evidence 'gate_status.txt' 'HOLD'
    Write-Evidence 'failure.txt' (($_ | Out-String))
    Write-Host "`nE06-16 FINAL FREEZE GATE HOLD" -ForegroundColor Red
    Write-Host $_
    Write-Host "Evidence: $Evidence"
    exit 2
}
finally {
    foreach ($n in $EnvNames) { [Environment]::SetEnvironmentVariable($n,$EnvBackup[$n],'Process') }
}

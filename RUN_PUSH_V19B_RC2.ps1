param(
  [string]$SourceRoot = $PSScriptRoot,
  [string]$RepoUrl = 'https://github.com/kaiwenzhang1023-oss/industrial-ai-paas-lab.git',
  [string]$Branch = 'v19-version-b-preview'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $SourceRoot).Path
$Manifest = Join-Path $Root 'RC2_FILE_SHA256.txt'
if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) { throw 'HOLD_RC2_MANIFEST_NOT_FOUND' }
$lines = @(Get-Content -LiteralPath $Manifest -Encoding UTF8)
$verified = 0
foreach ($line in $lines) {
 if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw 'HOLD_MANIFEST_FORMAT' }
 $digest = $Matches[1]; $rel = $Matches[2]
 if ($rel -match '(^|/)(\.git|\.env)(/|$)' -or $rel -match '\.(pyc|pfx|pem|key)$') {throw 'HOLD_SENSITIVE_OR_GENERATED_FILE'}
 $file = Join-Path $Root ($rel.Replace('/','\'))
 if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "HOLD_FILE_MISSING_$rel" }
 if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) { throw "HOLD_HASH_MISMATCH_$rel" }
 $verified++
}
Write-Host "RC2_SOURCE_HASHES=PASS ($verified files)"
$Git = (Get-Command git.exe -ErrorAction Stop).Source
$Temp = Join-Path ([IO.Path]::GetTempPath()) ('v19b-rc2-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Temp -Force | Out-Null
try {
 # Native stderr is not an exception in Git: use LASTEXITCODE, not PowerShell's error stream.
 $ErrorActionPreference='Continue'
 & $Git clone --single-branch --branch $Branch --depth 1 $RepoUrl $Temp
 if ($LASTEXITCODE -ne 0) { throw 'HOLD_GITHUB_CLONE_OR_AUTH' }
 $ErrorActionPreference='Stop'
 foreach($line in $lines) {
  $null = $line -match '^([0-9a-f]{64})  (.+)$'; $rel=$Matches[2]
  $from=Join-Path $Root ($rel.Replace('/','\'))
  $to=Join-Path $Temp ($rel.Replace('/','\'))
  $dest=Split-Path -Parent $to
  if(-not (Test-Path -LiteralPath $dest)){New-Item -Path $dest -ItemType Directory -Force | Out-Null}
  Copy-Item -LiteralPath $from -Destination $to -Force
 }
 Copy-Item -LiteralPath $Manifest -Destination (Join-Path $Temp 'RC2_FILE_SHA256.txt') -Force
 Push-Location $Temp
 try {
  $ErrorActionPreference='Continue'
  & $Git add --all
  if($LASTEXITCODE -ne 0){throw 'HOLD_GIT_ADD'}
  $changes = (& $Git status --porcelain)
  if($LASTEXITCODE -ne 0){throw 'HOLD_GIT_STATUS'}
  if($changes){
    & $Git -c user.name='Version B Preview Release' -c user.email='preview-release@users.noreply.github.com' commit -m 'Cloud RC2: integrated enterprise workspace, sessions and readiness regression'
    if($LASTEXITCODE -ne 0){throw 'HOLD_GIT_COMMIT'}
    & $Git push origin "HEAD:refs/heads/$Branch"
    if($LASTEXITCODE -ne 0){throw 'HOLD_GIT_PUSH_AUTH_OR_REMOTE_ADVANCED'}
  }
  & $Git rev-parse HEAD
  if($LASTEXITCODE -ne 0){throw 'HOLD_COMMIT_VERIFY'}
  Write-Host 'RC2_GITHUB_PUSH=PASS' -ForegroundColor Green
  Write-Host "BRANCH=$Branch"
  Write-Host "REPOSITORY=https://github.com/kaiwenzhang1023-oss/industrial-ai-paas-lab/tree/$Branch"
 } finally { Pop-Location }
} finally {
 $ErrorActionPreference='Continue'
 if(Test-Path -LiteralPath $Temp){Remove-Item -LiteralPath $Temp -Recurse -Force -ErrorAction SilentlyContinue}
}

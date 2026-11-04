param(
 [string]$SourceRoot = $PSScriptRoot,
 [string]$RepoUrl = 'https://github.com/kaiwenzhang1023-oss/industrial-ai-paas-lab.git',
 [string]$Branch = 'v19-version-b-preview'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Gate([bool]$Ok, [string]$Label) {
 if (-not $Ok) { throw "HOLD_$Label" }
 Write-Host "$Label=PASS"
}
$Root = (Resolve-Path -LiteralPath $SourceRoot).Path
Gate (Test-Path -LiteralPath (Join-Path $Root 'Dockerfile.version-b-preview')) 'PREVIEW_DOCKERFILE'
Gate (Test-Path -LiteralPath (Join-Path $Root 'preview_cloud\app.py')) 'PREVIEW_APP'
Gate (Test-Path -LiteralPath (Join-Path $Root 'RC4_PREVIEW_FILE_SHA256.txt')) 'SHA256_MANIFEST'
$manifest = Get-Content -LiteralPath (Join-Path $Root 'RC4_PREVIEW_FILE_SHA256.txt')
foreach ($line in $manifest) {
 if ($line -notmatch '^([0-9a-f]{64})  (.+)$') {throw "HOLD_INVALID_MANIFEST_LINE"}
 $relative = $Matches[2]; $digest = $Matches[1]
 $file = Join-Path $Root ($relative.Replace('/', '\'))
 if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {throw "HOLD_MISSING_FILE_$relative"}
 $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
 if ($actual -ne $digest) {throw "HOLD_HASH_MISMATCH_$relative"}
}
Write-Host 'PREVIEW_SOURCE_HASHES=PASS'
$Git = Get-Command git.exe -ErrorAction Stop
& $Git.Source --version
if ($LASTEXITCODE -ne 0) {throw 'HOLD_GIT_NOT_AVAILABLE'}
Push-Location $Root
try {
 if (Test-Path -LiteralPath (Join-Path $Root '.git')) {throw 'HOLD_SOURCE_IS_ALREADY_GIT_REPO'}
 & $Git.Source init -b $Branch
 if ($LASTEXITCODE -ne 0) {throw 'HOLD_GIT_INIT'}
 & $Git.Source remote add origin $RepoUrl
 if ($LASTEXITCODE -ne 0) {throw 'HOLD_GIT_REMOTE'}
 & $Git.Source add --all
 if ($LASTEXITCODE -ne 0) {throw 'HOLD_GIT_ADD'}
 & $Git.Source -c user.name='Version B Preview Release' -c user.email='preview-release@users.noreply.github.com' commit -m 'Version B isolated Render and Neon preview candidate'
 if ($LASTEXITCODE -ne 0) {throw 'HOLD_GIT_COMMIT'}
 & $Git.Source push --set-upstream origin "HEAD:refs/heads/$Branch"
 if ($LASTEXITCODE -ne 0) {throw 'HOLD_GIT_PUSH_AUTH_OR_BRANCH_CONFLICT'}
 Write-Host 'VERSION_B_GITHUB_PREVIEW_PUSH=PASS'
 Write-Host "BRANCH=$Branch"
 Write-Host "REPOSITORY=https://github.com/kaiwenzhang1023-oss/industrial-ai-paas-lab/tree/$Branch"
} finally {Pop-Location}

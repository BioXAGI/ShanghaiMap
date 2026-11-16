param(
    [int]$Port = 8081,
    [string]$OAuthToken = '',
    [string]$ImportCandidates = ''
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$runArgs = @('scripts/local_dashboard.py', '--port', "$Port")
if ($OAuthToken) { $runArgs += @('--oauth-token', $OAuthToken) }
if ($ImportCandidates) { $runArgs += @('--import-candidates', $ImportCandidates) }
python @runArgs

[CmdletBinding()]
param(
    [ValidateSet("local", "staging", "production")]
    [string]$Environment = "local",
    [string]$ImageReference,
    [switch]$ConfirmProduction,
    [switch]$SkipIngress
)

$ErrorActionPreference = "Stop"
$deployScript = Join-Path $PSScriptRoot "../../k8s/scripts/deploy.ps1"
& $deployScript -Environment $Environment -ImageReference $ImageReference `
    -ConfirmProduction:$ConfirmProduction -SkipIngress:$SkipIngress
if ($LASTEXITCODE -ne 0) {
    throw "Deployment failed with exit code $LASTEXITCODE"
}

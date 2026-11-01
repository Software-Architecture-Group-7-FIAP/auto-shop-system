[CmdletBinding()]
param(
    [ValidateSet("local", "staging", "production")]
    [string]$Environment = "local",
    [string]$SecretName = "auto-shop-secrets"
)

$ErrorActionPreference = "Stop"

function Test-PlaceholderValue {
    param([string]$Value)

    $patterns = @("__.*__", "replace-with", "change-me", "seu_", "sua_", "your_",
                  "example\.com", "^password$", "^senha$", "local-development-token",
                  "local-secret-change-me", "replace-with-")

    foreach ($pattern in $patterns) {
        if ($Value -imatch $pattern) { return $true }
    }
    return $false
}

if ($Environment -eq "local") {
    # Validate local secret file
    $secretFile = Join-Path (Split-Path $PSScriptRoot) "overlays/local/secrets.env"

    if (-not (Test-Path $secretFile)) {
        Write-Error "Local secret file not found: $secretFile"
        exit 1
    }

    $content = Get-Content -Raw -LiteralPath $secretFile
    $secretValues = ConvertFrom-StringData $content

    foreach ($entry in $secretValues.GetEnumerator()) {
        if (Test-PlaceholderValue $entry.Value) {
            Write-Error "Secret file contains placeholder in key '$($entry.Name)'"
            exit 1
        }
    }

    Write-Host "✓ Local secret file validated (no placeholders)" -ForegroundColor Green

} else {
    # Validate pre-provisioned cluster secret
    $secretCheck = & kubectl get secret $SecretName --namespace auto-shop -o name 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Secret '$SecretName' not found in cluster"
        exit 1
    }

    $requiredKeys = @("DATABASE_URL", "SECRET_KEY", "INVERTEXTO_API_TOKEN")
    foreach ($key in $requiredKeys) {
        $encodedValue = & kubectl get secret $SecretName --namespace auto-shop `
                          --output "jsonpath={.data.$key}" 2>&1

        if ($LASTEXITCODE -ne 0 -or -not $encodedValue) {
            Write-Error "Required secret key missing: $key"
            exit 1
        }

        $decodedValue = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedValue))

        if (Test-PlaceholderValue $decodedValue) {
            Write-Error "Secret key '$key' contains a placeholder value"
            exit 1
        }

        if ($key -eq "SECRET_KEY" -and $decodedValue.Length -lt 32) {
            Write-Error "SECRET_KEY must be at least 32 characters"
            exit 1
        }
    }

    Write-Host "✓ All secret keys validated successfully" -ForegroundColor Green
}

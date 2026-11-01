[CmdletBinding()]
param(
    [ValidateSet("local", "staging", "production")]
    [string]$Environment = "local",
    [string]$ImageReference,
    [switch]$ConfirmProduction,
    [switch]$SkipIngress
)

$ErrorActionPreference = "Stop"
$namespace = switch ($Environment) {
    "local" { "auto-shop" }
    "staging" { "auto-shop-hml" }
    "production" { "auto-shop-prd" }
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$overlayRoot = Join-Path $repoRoot "k8s/overlays/$Environment"
$tempFiles = [System.Collections.Generic.List[string]]::new()
$mutex = $null
$portForwardProcess = $null
$migrationJobName = $null
$seedJobName = $null
$newRelicK8sChart = "newrelic/nri-bundle"
$newRelicK8sChartVersion = "8.0.39"
$newRelicK8sChartSha256 = "96eb019f7c78e1e746e0ba170b7e656e437ae3f7bfe7203f812e750511db108f"
$newRelicK8sRelease = "auto-shop-new-relic"

function Invoke-RequiredCommand {
    param(
        [Parameter(Mandatory)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    $output = & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
    return ($output -join [Environment]::NewLine).Trim()
}

function Require-Tool {
    param([Parameter(Mandatory)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required tool is not available: $Name"
    }
}

function Test-ReleaseImage {
    param([Parameter(Mandatory)][string]$Reference)

    if ($Reference -match "@sha256:[0-9a-f]{64}$") {
        return $true
    }
    if ($Reference -match ":sha-[0-9a-f]{7,40}$") {
        return $true
    }
    return $Reference -match ":[0-9a-f]{7,64}$"
}

function Get-ReleaseSuffix {
    param(
        [Parameter(Mandatory)][string]$Reference,
        [Parameter(Mandatory)][string]$SessionId
    )

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes("$Reference`:$SessionId")
        $hash = $sha256.ComputeHash($bytes)
        return [BitConverter]::ToString($hash).Replace("-", "").ToLowerInvariant().Substring(0, 12)
    } finally {
        $sha256.Dispose()
    }
}

function Get-RenderedPhase {
    param([Parameter(Mandatory)][string]$Phase)

    $phasePath = Join-Path $overlayRoot $Phase
    $rendered = Invoke-CapturedCommand "kubectl" @("kustomize", $phasePath)
    $rendered = $rendered.Replace(
        "registry.example.com/auto-shop-system:__IMAGE_TAG__",
        $ImageReference
    )
    $rendered = $rendered.Replace(
        "auto-shop-system:__IMAGE_TAG__",
        $ImageReference
    )
    $rendered = $rendered.Replace(
        "auto-shop-system:local",
        $ImageReference
    )
    $rendered = $rendered.Replace("__APP_VERSION__", $ImageReference)
    if ($rendered.Contains("__IMAGE_TAG__")) {
        throw "Unresolved image tag in $Environment/$Phase"
    }
    if ($rendered.Contains("__APP_VERSION__")) {
        throw "Unresolved application version in $Environment/$Phase"
    }
    if ($Phase -eq "migration") {
        $rendered = $rendered.Replace("name: auto-shop-migrate", "name: $migrationJobName")
    }
    if ($Phase -eq "seed") {
        $rendered = $rendered.Replace("name: auto-shop-seed", "name: $seedJobName")
        $allowPrdSeed = if ($env:ALLOW_SYNTHETIC_SEED_IN_PRD -eq "true") { "true" } else { "false" }
        $rendered = $rendered.Replace("__ALLOW_SYNTHETIC_SEED_IN_PRD__", $allowPrdSeed)
        if ($rendered.Contains("__ALLOW_SYNTHETIC_SEED_IN_PRD__")) {
            throw "Unresolved production synthetic seed authorization"
        }
    }
    return $rendered
}

function Apply-RenderedPhase {
    param([Parameter(Mandatory)][string]$Phase)

    $rendered = Get-RenderedPhase $Phase
    $tempFile = [System.IO.Path]::GetTempFileName()
    $tempFiles.Add($tempFile)
    [System.IO.File]::WriteAllText($tempFile, $rendered)
    Invoke-RequiredCommand "kubectl" @("apply", "--filename", $tempFile)
}

function Test-SecretKeys {
    param(
        [Parameter(Mandatory)][string[]]$Keys
    )

    foreach ($key in $Keys) {
        $value = Invoke-CapturedCommand "kubectl" @(
            "get", "secret", "auto-shop-secrets", "--namespace", $namespace,
            "--output", "jsonpath={.data.$key}"
        )
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "Secret auto-shop-secrets is missing required key $key"
        }
        $decoded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($value))
        if ($decoded -match '(?i)__|replace-with|change-me|seu_|sua_|your_|example\.com') {
            throw "Secret auto-shop-secrets contains a placeholder in key $key"
        }
        if ($key -eq "SECRET_KEY" -and $decoded.Length -lt 32) {
            throw "Secret auto-shop-secrets SECRET_KEY is shorter than 32 characters"
        }
    }
}

function Ensure-Secret {
    $secretFile = Join-Path $overlayRoot "secrets.env"
    if ($Environment -eq "local") {
        if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
            throw "Create the ignored local secret file from k8s/examples/secrets.example.env before deploying"
        }
        $localSecretContent = Get-Content -Raw -LiteralPath $secretFile
        if ($localSecretContent -match '(?i)__|replace-with|change-me|seu_|sua_|your_|example\.com') {
            throw "The local secret file still contains a placeholder"
        }
        $secretValues = ConvertFrom-StringData $localSecretContent
        foreach ($key in @("DB_NAME", "DB_USER", "DB_PASSWORD", "SECRET_KEY")) {
            if ([string]::IsNullOrWhiteSpace($secretValues.$key)) {
                throw "The local secret file is missing required key $key"
            }
        }
        $databaseUrl = "postgresql://{0}:{1}@postgres-service:5432/{2}" -f `
            [Uri]::EscapeDataString($secretValues.DB_USER),
            [Uri]::EscapeDataString($secretValues.DB_PASSWORD),
            [Uri]::EscapeDataString($secretValues.DB_NAME)
        $materializedSecretFile = [System.IO.Path]::GetTempFileName()
        $tempFiles.Add($materializedSecretFile)
        $materializedSecretContent = $localSecretContent.TrimEnd() + "`nDATABASE_URL=$databaseUrl`n"
        [System.IO.File]::WriteAllText($materializedSecretFile, $materializedSecretContent)
        $secretManifest = Invoke-CapturedCommand "kubectl" @(
            "create", "secret", "generic", "auto-shop-secrets",
            "--namespace", $namespace,
            "--from-env-file=$materializedSecretFile",
            "--dry-run=client",
            "--output", "yaml"
        )
        $tempFile = [System.IO.Path]::GetTempFileName()
        $tempFiles.Add($tempFile)
        [System.IO.File]::WriteAllText($tempFile, $secretManifest)
        Invoke-RequiredCommand "kubectl" @("apply", "--filename", $tempFile)
        Test-SecretKeys @("DATABASE_URL", "DB_NAME", "DB_USER", "DB_PASSWORD", "SECRET_KEY", "DEMO_ADMIN_PASSWORD")
        return
    }

    Invoke-RequiredCommand "kubectl" @("get", "secret", "auto-shop-secrets", "--namespace", $namespace, "--output", "name")
    Test-SecretKeys @("DATABASE_URL", "SECRET_KEY", "INVERTEXTO_API_TOKEN", "SMTP_USER", "SMTP_PASSWORD", "DEMO_ADMIN_PASSWORD")
    $tlsSecret = if ($Environment -eq "staging") { "staging-auto-shop-tls" } else { "auto-shop-tls" }
    Invoke-RequiredCommand "kubectl" @("get", "secret", $tlsSecret, "--namespace", $namespace, "--output", "name")
}

function Ensure-NewRelicSecret {
    if ($Environment -ne "staging") {
        return
    }
    if ([string]::IsNullOrWhiteSpace($env:NEW_RELIC_LICENSE_KEY)) {
        throw "The HML New Relic license key is required"
    }

    $licenseFile = [System.IO.Path]::GetTempFileName()
    $tempFiles.Add($licenseFile)
    [System.IO.File]::WriteAllText($licenseFile, $env:NEW_RELIC_LICENSE_KEY)
    & kubectl @(
        "create", "secret", "generic", "auto-shop-new-relic",
        "--namespace", $namespace,
        "--from-file", "NEW_RELIC_LICENSE_KEY=$licenseFile",
        "--dry-run=client", "--output=yaml"
    ) | & kubectl apply --filename=-
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to materialize the New Relic Kubernetes Secret"
    }
    Remove-Item Env:NEW_RELIC_LICENSE_KEY -ErrorAction SilentlyContinue
}

function Install-NewRelicKubernetes {
    if ($Environment -ne "staging") {
        return
    }

    Require-Tool "helm"
    Require-Tool "curl.exe"
    $valuesFile = Join-Path $repoRoot "k8s/observability/new-relic/values-staging.yaml"
    $chartFile = [System.IO.Path]::GetTempFileName() + ".tgz"
    $tempFiles.Add($chartFile)
    $licenseData = Invoke-CapturedCommand "kubectl" @(
        "get", "secret", "auto-shop-new-relic", "--namespace", $namespace,
        "--output", "jsonpath={.data.NEW_RELIC_LICENSE_KEY}"
    )
    if ([string]::IsNullOrWhiteSpace($licenseData)) {
        throw "Secret auto-shop-new-relic is missing NEW_RELIC_LICENSE_KEY"
    }

    Invoke-RequiredCommand "curl.exe" @(
        "--fail", "--location", "--silent", "--show-error",
        "--output", $chartFile,
        "https://github.com/newrelic/helm-charts/releases/download/nri-bundle-$newRelicK8sChartVersion/nri-bundle-$newRelicK8sChartVersion.tgz"
    )
    $actualChartHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $chartFile).Hash.ToLowerInvariant()
    if ($actualChartHash -ne $newRelicK8sChartSha256) {
        throw "New Relic Kubernetes chart checksum mismatch"
    }
    Invoke-RequiredCommand "helm" @(
        "upgrade", "--install", $newRelicK8sRelease, $chartFile,
        "--namespace", $namespace,
        "--values", $valuesFile,
        "--atomic", "--wait", "--timeout", "10m"
    )
}

function Wait-ForMigration {
    try {
        Invoke-RequiredCommand "kubectl" @(
            "wait", "--for=condition=complete", "job/$migrationJobName",
            "--namespace", $namespace, "--timeout=300s"
        )
    } catch {
        $logs = & kubectl logs job/$migrationJobName --namespace $namespace --tail=100 2>&1
        $sanitized = ($logs -join [Environment]::NewLine) -replace '(?i)(postgres(?:ql)?://)[^\s''"]+', '$1[REDACTED]'
        Write-Error "Migration failed. Sanitized migration logs:`n$sanitized"
        throw
    }
}

function Wait-ForSeed {
    try {
        Invoke-RequiredCommand "kubectl" @(
            "wait", "--for=condition=complete", "job/$seedJobName",
            "--namespace", $namespace, "--timeout=300s"
        )
    } catch {
        $logs = & kubectl logs job/$seedJobName --namespace $namespace --tail=100 2>&1
        $sanitized = ($logs -join [Environment]::NewLine) -replace '(?i)(postgres(?:ql)?://)[^\s''"]+', '$1[REDACTED]'
        Write-Error "Synthetic seed failed. Sanitized seed logs:`n$sanitized"
        throw
    }
}

function Invoke-SmokeTest {
    $port = 18000
    $portForwardProcess = Start-Process -FilePath "kubectl" -WindowStyle Hidden -PassThru -ArgumentList @(
        "port-forward", "service/auto-shop-backend-service", "${port}:80", "--namespace", $namespace
    )
    try {
        $deadline = (Get-Date).AddSeconds(30)
        do {
            Start-Sleep -Milliseconds 500
            try {
                $live = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/health/live" -TimeoutSec 3
                $ready = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/health/ready" -TimeoutSec 3
                $docs = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/docs" -TimeoutSec 3
                if ($live.StatusCode -eq 200 -and $ready.StatusCode -eq 200 -and $docs.StatusCode -eq 200) {
                    return
                }
            } catch {
                if ((Get-Date) -ge $deadline) {
                    throw "Smoke test timed out"
                }
            }
        } while ((Get-Date) -lt $deadline)
        throw "Smoke test timed out"
    } finally {
        if ($null -ne $portForwardProcess -and -not $portForwardProcess.HasExited) {
            Stop-Process -Id $portForwardProcess.Id -Force
        }
    }
}

try {
    Require-Tool "kubectl"
    if (-not (Test-Path -LiteralPath $overlayRoot -PathType Container)) {
        throw "Overlay does not exist: $overlayRoot"
    }
    if ($Environment -eq "production" -and -not $ConfirmProduction) {
        throw "Production deploy requires -ConfirmProduction"
    }
    if ($Environment -eq "production" -and $env:ALLOW_SYNTHETIC_SEED_IN_PRD -ne "true") {
        throw "Production synthetic seed requires ALLOW_SYNTHETIC_SEED_IN_PRD=true for this deployment"
    }

    if ($Environment -eq "local") {
        if ([string]::IsNullOrWhiteSpace($ImageReference)) {
            $localSuffix = [Guid]::NewGuid().ToString("N").Substring(0, 12)
            $ImageReference = "auto-shop-system:local-$localSuffix"
            Require-Tool "docker"
            Invoke-RequiredCommand "docker" @("build", "--tag", $ImageReference, $repoRoot)
        } else {
            Require-Tool "docker"
            Invoke-RequiredCommand "docker" @("image", "inspect", $ImageReference)
        }
        if (Get-Command kind -ErrorAction SilentlyContinue) {
            Invoke-RequiredCommand "kind" @("load", "docker-image", $ImageReference)
        }
    } elseif ([string]::IsNullOrWhiteSpace($ImageReference) -or -not (Test-ReleaseImage $ImageReference)) {
        throw "Staging and production require an immutable image digest or a hexadecimal commit-SHA tag"
    }

    $mutex = [System.Threading.Mutex]::new($false, "Local\AutoShopDeploy-$Environment")
    if (-not $mutex.WaitOne(0)) {
        throw "Another deployment is already running for $Environment"
    }

    $context = Invoke-CapturedCommand "kubectl" @("config", "current-context")
    if ([string]::IsNullOrWhiteSpace($context)) {
        throw "kubectl has no active context"
    }
    $lifecycleSessionId = if ([string]::IsNullOrWhiteSpace($env:LIFECYCLE_SESSION_ID)) {
        "local-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
    } else {
        $env:LIFECYCLE_SESSION_ID
    }
    $releaseSuffix = Get-ReleaseSuffix $ImageReference $lifecycleSessionId
    $migrationJobName = "auto-shop-migrate-$releaseSuffix"
    $seedJobName = "auto-shop-seed-$releaseSuffix"

    $namespaceManifest = Invoke-CapturedCommand "kubectl" @(
        "create", "namespace", $namespace, "--dry-run=client", "--output=yaml"
    )
    $namespaceFile = [System.IO.Path]::GetTempFileName()
    $tempFiles.Add($namespaceFile)
    [System.IO.File]::WriteAllText($namespaceFile, $namespaceManifest)
    Invoke-RequiredCommand "kubectl" @("apply", "--filename", $namespaceFile)
    Ensure-Secret
    Apply-RenderedPhase "foundation"
    Ensure-NewRelicSecret

    if ($Environment -eq "local") {
        Invoke-RequiredCommand "kubectl" @("rollout", "status", "deployment/postgres", "--namespace", $namespace, "--timeout=180s")
    }

    Apply-RenderedPhase "migration"
    Wait-ForMigration

    Apply-RenderedPhase "seed"
    Wait-ForSeed

    Apply-RenderedPhase "app"
    Invoke-RequiredCommand "kubectl" @("rollout", "status", "deployment/auto-shop-backend", "--namespace", $namespace, "--timeout=300s")
    Install-NewRelicKubernetes

    if (-not $SkipIngress) {
        Apply-RenderedPhase "ingress"
    }

    Invoke-SmokeTest
    Write-Host "Auto Shop $Environment deployment completed successfully." -ForegroundColor Green
} finally {
    foreach ($tempFile in $tempFiles) {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
        }
    }
    if ($null -ne $mutex) {
        try { $mutex.ReleaseMutex() } catch { }
        $mutex.Dispose()
    }
}

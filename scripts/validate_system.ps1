[CmdletBinding()]
param(
    [switch]$Coverage,
    [switch]$Security,
    [switch]$Database,
    [switch]$Frontend
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-ValidationStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Falha na etapa: $Name (exit code $LASTEXITCODE)"
    }
}

Push-Location $repoRoot
try {
    Invoke-ValidationStep "Backend: suíte completa" {
        poetry run pytest -q
    }

    if ($Coverage) {
        Invoke-ValidationStep "Backend: cobertura de branches" {
            poetry run pytest --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=80
        }
    }

    Invoke-ValidationStep "Configuração: defaults inseguros" {
        poetry run python scripts/check_unsafe_defaults.py
    }

    if ($Database) {
        Invoke-ValidationStep "Banco: aplicar migrations" {
            poetry run alembic upgrade head
        }
        Invoke-ValidationStep "Banco: verificar divergência de migrations" {
            poetry run alembic check
        }
    }

    if ($Security) {
        Invoke-ValidationStep "Segurança: Bandit" {
            poetry run bandit -r src -ll
        }
        Invoke-ValidationStep "Segurança: pip-audit" {
            poetry run pip-audit
        }
    }

    if ($Frontend) {
        Push-Location (Join-Path $repoRoot "frontend")
        try {
            Invoke-ValidationStep "Frontend: dependências" {
                npm ci
            }
            Invoke-ValidationStep "Frontend: TypeScript dos testes" {
                npx tsc -p tsconfig.spec.json --noEmit
            }
            Invoke-ValidationStep "Frontend: build" {
                npm run build
            }
            Invoke-ValidationStep "Frontend: Karma" {
                npm test -- --watch=false --browsers=ChromeHeadless
            }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "`nValidação concluída com sucesso." -ForegroundColor Green
}
finally {
    Pop-Location
}

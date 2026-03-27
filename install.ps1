param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step {
    param([string]$Message)
    Write-Output ""
    Write-Output $Message
}

function Invoke-Action {
    param(
        [scriptblock]$Action,
        [string]$Preview
    )

    if ($DryRun) {
        Write-Output ("  [dry-run] " + $Preview)
    } else {
        & $Action
    }
}

function Copy-IfMissing {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (Test-Path -LiteralPath $Destination) {
        Write-Output ("  [exists] " + $Destination)
        return
    }
    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Output ("  [missing template] " + $Source)
        return
    }
    if ($DryRun) {
        Write-Output ("  [dry-run] Copy-Item " + $Source + " " + $Destination)
        return
    }
    Copy-Item -LiteralPath $Source -Destination $Destination
    Write-Output ("  [initialized] " + $Destination)
}

$skillsSrc = Join-Path $ScriptDir "claude-assets\skills"
$skillsDst = Join-Path $HOME ".claude\skills"
$req = Join-Path $ScriptDir "jira-mcp\requirements.txt"
$hook = Join-Path $ScriptDir "claude-assets\hooks\svn_jira_transition_hook.py"
$skillDir = Join-Path $ScriptDir "claude-assets\skills\daily-workflow"
$configTemplate = Join-Path $skillDir "config.example.json"
$mappingTemplate = Join-Path $skillDir "svn-mapping-template.json"
$verifyTemplate = Join-Path $skillDir "verification.template.json"
$configFile = Join-Path $skillDir "config.json"
$mappingFile = Join-Path $skillDir "svn-mapping.json"
$verifyFile = Join-Path $skillDir "verification.json"
$validator = Join-Path $skillDir "validate_daily_workflow_config.py"

Write-Step "=== Install Skills ==="
if (-not (Test-Path -LiteralPath $skillsSrc)) {
    Write-Output ("Skip: skill directory not found (" + $skillsSrc + ")")
} else {
    Invoke-Action -Preview ("New-Item -ItemType Directory -Force " + $skillsDst) -Action {
        New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null
    }
    $count = 0
    foreach ($dir in Get-ChildItem -LiteralPath $skillsSrc -Directory) {
        $targetDir = Join-Path $skillsDst $dir.Name
        Write-Output ("  -> " + $dir.Name)
        Invoke-Action -Preview ("New-Item -ItemType Directory -Force " + $targetDir) -Action {
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        }
        Invoke-Action -Preview ("Copy-Item " + $dir.FullName + "\* " + $targetDir + " -Recurse -Force") -Action {
            Copy-Item -Path (Join-Path $dir.FullName "*") -Destination $targetDir -Recurse -Force
        }
        $count++
    }
    Write-Output ("  Installed " + $count + " skill(s)")
}

Write-Step "=== Install MCP Dependencies ==="
if (-not (Test-Path -LiteralPath $req)) {
    Write-Output ("Skip: requirements file not found (" + $req + ")")
} else {
    Write-Output ("  pip install -r " + $req)
    if ($DryRun) {
        Write-Output ("  [dry-run] pip install -r " + $req + " -q")
    } else {
        & pip install -r $req -q
        Write-Output "  Dependencies installed"
    }
}

Write-Step "=== Check JIRA Environment Variables ==="
$requiredVars = @("JIRA_BASE_URL", "JIRA_USERNAME", "JIRA_PASSWORD")
$optionalVars = @("JIRA_API_PATH", "JIRA_TIMEOUT")
$missing = 0
foreach ($var in $requiredVars) {
    $value = (Get-Item ("Env:" + $var) -ErrorAction SilentlyContinue).Value
    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-Output ("  [missing] " + $var + " (required)")
        $missing++
    } else {
        Write-Output ("  [OK]   " + $var)
    }
}
foreach ($var in $optionalVars) {
    $value = (Get-Item ("Env:" + $var) -ErrorAction SilentlyContinue).Value
    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-Output ("  [default] " + $var + " (not set, code default will be used)")
    } else {
        Write-Output ("  [OK]   " + $var)
    }
}
if ($missing -gt 0) {
    Write-Output ""
    Write-Output ("Warning: " + $missing + " required JIRA env var(s) are missing; MCP startup may fail")
    Write-Output "Set them in system environment variables or .env and run again"
}

Write-Step "=== Check Hooks ==="
if (Test-Path -LiteralPath $hook) {
    Write-Output "  [OK] svn_jira_transition_hook.py found"
    Write-Output ("       Path: " + $hook)
    Write-Output "       Referenced by .claude/settings.json"
} else {
    Write-Output ("  [missing] " + $hook)
}

Write-Step "=== Initialize daily-workflow Config ==="
Copy-IfMissing -Source $configTemplate -Destination $configFile
Copy-IfMissing -Source $mappingTemplate -Destination $mappingFile
Copy-IfMissing -Source $verifyTemplate -Destination $verifyFile

Write-Step "=== Validate daily-workflow Config ==="
if (-not (Test-Path -LiteralPath $validator)) {
    Write-Output ("Skip: validator not found (" + $validator + ")")
} elseif (-not (Test-Path -LiteralPath $configFile)) {
    Write-Output ("Skip: local config not found (" + $configFile + ")")
    Write-Output "      Fill config.json / svn-mapping.json / verification.json first"
} elseif ($DryRun) {
    Write-Output ("  [dry-run] python " + $validator)
} else {
    Write-Output ("  python " + $validator)
    & python $validator
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  Config validation passed"
    } else {
        Write-Output "  Warning: daily-workflow config validation failed; fix it before use"
    }
}

Write-Output ""
if ($DryRun) {
    Write-Output "[dry-run] Preview complete. Run powershell -ExecutionPolicy Bypass -File .\install.ps1 for actual install"
} else {
    Write-Output "Install complete"
}

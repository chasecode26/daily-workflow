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

function Initialize-OrUpdateConfig {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Output ("  [缺失示例] " + $Source)
        return $false
    }

    if (-not (Test-Path -LiteralPath $Destination)) {
        if ($DryRun) {
            Write-Output ("  [dry-run] Copy-Item " + $Source + " " + $Destination)
        } else {
            Copy-Item -LiteralPath $Source -Destination $Destination
            Write-Output ("  [已初始化] " + $Destination)
        }
        return $true
    }

    if ($DryRun) {
        Write-Output ("  [dry-run] 配置已存在，将询问是否覆盖: " + $Destination)
        return $false
    }

    $answer = Read-Host ("  [已存在] " + $Destination + "，是否用示例覆盖？[y/N]")
    if ($answer -match '^(y|Y|yes|YES)$') {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        Write-Output ("  [已覆盖] " + $Destination)
        return $true
    }

    Write-Output ("  [保留原配置] " + $Destination)
    return $false
}

function Test-IsExampleConfig {
    param(
        [string]$Source,
        [string]$Destination
    )

    if ((-not (Test-Path -LiteralPath $Source)) -or (-not (Test-Path -LiteralPath $Destination))) {
        return $false
    }

    try {
        $sourceJson = Get-Content -LiteralPath $Source -Raw -Encoding UTF8 | ConvertFrom-Json | ConvertTo-Json -Depth 100 -Compress
        $destinationJson = Get-Content -LiteralPath $Destination -Raw -Encoding UTF8 | ConvertFrom-Json | ConvertTo-Json -Depth 100 -Compress
        return $sourceJson -eq $destinationJson
    } catch {
        return $false
    }
}

function Test-ConfigNeedsSetup {
    param(
        [string]$JiraConfigPath,
        [string]$MappingConfigPath
    )

    try {
        $jiraConfig = Get-Content -LiteralPath $JiraConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $mappingConfig = Get-Content -LiteralPath $MappingConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $false
    }

    if (
        $jiraConfig.baseUrl -eq "https://jira.example.com" -or
        $jiraConfig.username -eq "your_username" -or
        $jiraConfig.password -eq "your_password"
    ) {
        return $true
    }

    foreach ($mapping in ($mappingConfig.mappings | Where-Object { $_ -ne $null })) {
        $comment = [string]$mapping._comment
        $projectName = [string]$mapping.projectName
        $frontendPath = [string]$mapping.frontendPath
        $backendPath = [string]$mapping.backendPath
        $rootPath = [string]$mapping.rootPath

        if (
            $comment.Contains("示例") -or
            $projectName -eq "你的JIRA项目名" -or
            $frontendPath.Contains("your-project") -or
            $backendPath.Contains("your-project") -or
            $rootPath.Contains("your-project")
        ) {
            return $true
        }
    }

    return $false
}

function Resolve-SkillsDestination {
    $explicitRoot = [string]$env:DAILY_WORKFLOW_SKILLS_HOME
    if ($explicitRoot.Trim()) {
        return $explicitRoot
    }

    $codexHome = [string]$env:CODEX_HOME
    if ($codexHome.Trim()) {
        return (Join-Path $codexHome "skills")
    }

    $codexSkills = Join-Path $HOME ".codex\skills"
    if (Test-Path -LiteralPath $codexSkills) {
        return $codexSkills
    }

    $claudeSkills = Join-Path $HOME ".claude\skills"
    if (Test-Path -LiteralPath $claudeSkills) {
        return $claudeSkills
    }

    return $codexSkills
}

$skillsSrc = Join-Path $ScriptDir "claude-assets\skills"
$skillsDst = Resolve-SkillsDestination
$req = Join-Path $ScriptDir "jira-mcp\requirements.txt"
$hook = Join-Path $ScriptDir "claude-assets\hooks\svn_jira_transition_hook.py"
$skillSrcDir = Join-Path $ScriptDir "claude-assets\skills\daily-workflow"
$skillTargetDir = Join-Path $skillsDst "daily-workflow"
$jiraExample = Join-Path $skillSrcDir "jira-config.example.json"
$jiraFile = Join-Path $skillTargetDir "jira-config.json"
$mappingExample = Join-Path $skillSrcDir "svn-mapping.example.json"
$mappingFile = Join-Path $skillTargetDir "svn-mapping.json"
$validator = Join-Path $skillSrcDir "validate_daily_workflow_config.py"
$configChanged = $false

Write-Step "=== 安装技能 ==="
if (-not (Test-Path -LiteralPath $skillsSrc)) {
    Write-Output ("跳过：技能目录不存在 (" + $skillsSrc + ")")
} else {
    Write-Output ("  安装目标: " + $skillsDst)
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
    Write-Output ("  已安装 " + $count + " 个技能")
}

Write-Step "=== 安装 JIRA MCP 依赖 ==="
if (-not (Test-Path -LiteralPath $req)) {
    Write-Output ("跳过：未找到依赖文件 (" + $req + ")")
} else {
    Write-Output ("  pip install -r " + $req)
    if ($DryRun) {
        Write-Output ("  [dry-run] pip install -r " + $req + " -q")
    } else {
        & pip install -r $req -q
        Write-Output "  依赖安装完成"
    }
}

Write-Step "=== 检查 Hook ==="
if (Test-Path -LiteralPath $hook) {
    Write-Output "  [已就绪] svn_jira_transition_hook.py"
    Write-Output ("           路径: " + $hook)
} else {
    Write-Output ("  [缺失] " + $hook)
}

Write-Step "=== 初始化 daily-workflow 本地配置 ==="
Invoke-Action -Preview ("New-Item -ItemType Directory -Force " + $skillTargetDir) -Action {
    New-Item -ItemType Directory -Force -Path $skillTargetDir | Out-Null
}
$configChanged = (Initialize-OrUpdateConfig -Source $jiraExample -Destination $jiraFile) -or $configChanged
$configChanged = (Initialize-OrUpdateConfig -Source $mappingExample -Destination $mappingFile) -or $configChanged
Write-Output ("  配置目录: " + $skillTargetDir)

Write-Step "=== 校验 daily-workflow 本地配置 ==="
if (-not (Test-Path -LiteralPath $validator)) {
    Write-Output ("跳过：未找到校验脚本 (" + $validator + ")")
} elseif ((-not (Test-Path -LiteralPath $jiraFile)) -or (-not (Test-Path -LiteralPath $mappingFile))) {
    Write-Output "跳过：未找到本地配置"
    Write-Output "      请先填写 jira-config.json 和 svn-mapping.json"
} elseif ($configChanged) {
    Write-Output "跳过：本次刚生成或覆盖了示例配置"
    Write-Output "      请先按实际环境修改 jira-config.json 和 svn-mapping.json"
    Write-Output "      修改完成后重新运行安装脚本，或手动执行校验脚本"
} elseif ((Test-IsExampleConfig -Source $jiraExample -Destination $jiraFile) -or (Test-IsExampleConfig -Source $mappingExample -Destination $mappingFile)) {
    Write-Output "跳过：检测到当前仍是示例配置"
    Write-Output "      请先按实际环境修改 jira-config.json 和 svn-mapping.json"
    Write-Output "      修改完成后重新运行安装脚本，或手动执行校验脚本"
} elseif (Test-ConfigNeedsSetup -JiraConfigPath $jiraFile -MappingConfigPath $mappingFile) {
    Write-Output "跳过：检测到配置里仍有占位示例内容"
    Write-Output "      请先按实际环境修改 jira-config.json 和 svn-mapping.json"
    Write-Output "      修改完成后重新运行安装脚本，或手动执行校验脚本"
} elseif ($DryRun) {
    Write-Output ("  [dry-run] python " + $validator + " --skill-dir """ + $skillTargetDir + """")
} else {
    Write-Output ("  python " + $validator + " --skill-dir """ + $skillTargetDir + """")
    & python $validator --skill-dir $skillTargetDir
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  配置校验通过"
    } else {
        Write-Output "  警告：配置校验未通过，请按提示修正后再使用"
    }
}

Write-Output ""
if ($DryRun) {
    Write-Output "[dry-run] 预览完成，运行 powershell -ExecutionPolicy Bypass -File .\install.ps1 正式安装"
} else {
    Write-Output "安装完成"
}


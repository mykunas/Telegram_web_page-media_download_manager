$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "========== $Message ==========" -ForegroundColor Cyan
}

function Assert-PathExists {
    param(
        [string]$TargetPath,
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        throw "[$Description] 路径不存在: $TargetPath"
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Step $Name
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "[$Name] 外部命令执行失败，退出码: $LASTEXITCODE"
    }
    Write-Host "[OK] $Name" -ForegroundColor Green
}

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return 'py'
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return 'python'
    }
    throw '未找到 Python 命令（py 或 python）'
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..') | Select-Object -ExpandProperty Path

$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendDir = Join-Path $RepoRoot 'backend'
$WorkerDir = Join-Path $RepoRoot 'app'
$DesktopDir = Join-Path $RepoRoot 'desktop'
$ToolsDir = Join-Path $RepoRoot 'tools'
$FFmpegSrc = Join-Path $ToolsDir 'ffmpeg\ffmpeg.exe'
$FFmpegDestDir = Join-Path $ToolsDir 'ffmpeg'

$BackendDistDir = Join-Path $BackendDir 'dist'
$WorkerDistDir = Join-Path $WorkerDir 'dist'

$BackendEntry = Join-Path $BackendDir 'run_backend.py'
$WorkerEntry = Join-Path $WorkerDir 'downloader.py'

Assert-PathExists -TargetPath $FrontendDir -Description 'frontend目录'
Assert-PathExists -TargetPath $BackendDir -Description 'backend目录'
Assert-PathExists -TargetPath $WorkerDir -Description 'worker目录'
Assert-PathExists -TargetPath $DesktopDir -Description 'desktop目录'
Assert-PathExists -TargetPath $BackendEntry -Description 'backend入口文件'
Assert-PathExists -TargetPath $WorkerEntry -Description 'worker入口文件'
Assert-PathExists -TargetPath $FFmpegSrc -Description 'ffmpeg.exe'

$PythonCmd = Resolve-PythonCommand

Invoke-Step -Name 'Step 1/5 构建前端 (npm run build)' -Action {
    Push-Location $FrontendDir
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
            Write-Host '[INFO] frontend/node_modules 不存在，先执行 npm install'
            npm install
        }
        npm run build
    }
    finally {
        Pop-Location
    }

    Assert-PathExists -TargetPath (Join-Path $FrontendDir 'dist\index.html') -Description '前端构建产物'
}

Invoke-Step -Name 'Step 2/5 使用 PyInstaller 打包 backend.exe' -Action {
    Push-Location $BackendDir
    try {
        & $PythonCmd -m PyInstaller --noconfirm --clean --onefile --name backend --distpath $BackendDistDir $BackendEntry
    }
    finally {
        Pop-Location
    }

    Assert-PathExists -TargetPath (Join-Path $BackendDistDir 'backend.exe') -Description 'backend.exe'
}

Invoke-Step -Name 'Step 3/5 使用 PyInstaller 打包 worker.exe' -Action {
    Push-Location $WorkerDir
    try {
        & $PythonCmd -m PyInstaller --noconfirm --clean --onefile --name worker --distpath $WorkerDistDir $WorkerEntry
    }
    finally {
        Pop-Location
    }

    Assert-PathExists -TargetPath (Join-Path $WorkerDistDir 'worker.exe') -Description 'worker.exe'
}

Invoke-Step -Name 'Step 4/5 拷贝 ffmpeg.exe' -Action {
    New-Item -ItemType Directory -Force -Path $FFmpegDestDir | Out-Null
    $ffmpegDest = Join-Path $FFmpegDestDir 'ffmpeg.exe'
    $srcFull = [System.IO.Path]::GetFullPath($FFmpegSrc)
    $destFull = [System.IO.Path]::GetFullPath($ffmpegDest)
    if ($srcFull -ne $destFull) {
        Copy-Item -LiteralPath $FFmpegSrc -Destination $ffmpegDest -Force
    }
    else {
        Write-Host '[INFO] ffmpeg 源路径与目标路径相同，跳过拷贝'
    }
    Assert-PathExists -TargetPath $ffmpegDest -Description 'ffmpeg目标文件'
}

Invoke-Step -Name 'Step 5/5 构建 Electron 安装包 (NSIS)' -Action {
    Push-Location $DesktopDir
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $DesktopDir 'node_modules'))) {
            Write-Host '[INFO] desktop/node_modules 不存在，先执行 npm install'
            npm install
        }

        npx electron-builder --config electron-builder.yml --win nsis
    }
    finally {
        Pop-Location
    }

    Assert-PathExists -TargetPath (Join-Path $DesktopDir 'dist') -Description 'Electron打包输出目录'
}

Write-Host ''
Write-Host '全部步骤执行完成。' -ForegroundColor Green
Write-Host "安装包输出目录: $DesktopDir\dist" -ForegroundColor Yellow

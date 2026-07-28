#Requires -Version 5.0
$ErrorActionPreference = "Stop"

try { chcp 65001 > $null } catch {}
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$OutputEncoding = [System.Text.Encoding]::UTF8

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls
} catch {}
$ProgressPreference = "SilentlyContinue"

$EnvName = "airicore"
$PyVersion = "3.11"

$PipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple"
$PipHost = "pypi.tuna.tsinghua.edu.cn"
$PlaywrightDownloadHost = "https://cdn.npmmirror.com/binaries/playwright"
$CondaMirror = "https://mirrors.tuna.tsinghua.edu.cn/anaconda"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $ProjectDir

Write-Host "==> AiriCore 一键部署 (Windows)"
Write-Host "    项目目录: $ProjectDir"

function Find-CondaHook {
    $candidates = @(
        (Join-Path $env:USERPROFILE "miniconda3\shell\condabin\conda-hook.ps1"),
        (Join-Path $env:USERPROFILE "anaconda3\shell\condabin\conda-hook.ps1"),
        "C:\ProgramData\miniconda3\shell\condabin\conda-hook.ps1",
        "C:\ProgramData\Anaconda3\shell\condabin\conda-hook.ps1"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd) {
        $base = (& conda info --base).Trim()
        $hook = Join-Path $base "shell\condabin\conda-hook.ps1"
        if (Test-Path $hook) { return $hook }
    }
    return $null
}

function Install-Miniconda {
    Write-Host "==> 未检测到 conda, 正在安装 Miniconda 到 $env:USERPROFILE\miniconda3"
    $installDir = Join-Path $env:USERPROFILE "miniconda3"
    $file = "Miniconda3-latest-Windows-x86_64.exe"
    $installer = Join-Path $env:TEMP "miniconda_installer.exe"
    Write-Host "    从镜像下载: $CondaMirror/miniconda/$file"
    try {
        Invoke-WebRequest -Uri "$CondaMirror/miniconda/$file" -OutFile $installer -UseBasicParsing
    } catch {
        Write-Host "    镜像下载失败, 回退官方源: https://repo.anaconda.com/miniconda/$file"
        Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/$file" -OutFile $installer -UseBasicParsing
    }
    if (-not (Test-Path $installer)) {
        throw "Miniconda 安装包下载失败 (镜像与官方源均不可用)。"
    }
    Write-Host "    正在静默安装 (可能需要几分钟)"
    Start-Process -FilePath $installer -ArgumentList @(
        "/InstallationType=JustMe", "/RegisterPython=0", "/S", "/D=$installDir"
    ) -Wait
    Remove-Item $installer -Force -ErrorAction SilentlyContinue
}

$hook = Find-CondaHook
if (-not $hook) {
    Install-Miniconda
    $hook = Find-CondaHook
}
if (-not $hook) {
    throw "安装后仍未找到 conda hook; 请打开 'Anaconda Prompt' 后重新运行。"
}

Write-Host "==> 使用 conda hook: $hook"
& $hook

$existing = & conda env list | Select-String -Pattern "^\s*$EnvName\s"
if ($existing) {
    Write-Host "==> 环境 '$EnvName' 已存在, 复用"
} else {
    $env:CONDA_SUBDIR = "win-64"
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "ARM64") {
        Write-Host "==> 检测到 Windows ARM64, 强制创建 win-64 (x64) 环境"
        Write-Host "    (playwright/aiohttp 等无 win-arm64 轮子, x64 经系统模拟运行, 兼容性最佳)"
    }
    Write-Host "==> 接受 conda 默认 channel 服务条款 (旧版本无此命令则忽略)"
    foreach ($ch in @(
        "https://repo.anaconda.com/pkgs/main",
        "https://repo.anaconda.com/pkgs/r",
        "https://repo.anaconda.com/pkgs/msys2"
    )) {
        try { conda tos accept --override-channels --channel $ch 2>$null | Out-Null } catch {}
    }
    Write-Host "==> 创建环境 '$EnvName' (python $PyVersion, win-64, 使用镜像 channel)"
    conda create -y -n $EnvName "python=$PyVersion" --override-channels -c "$CondaMirror/cloud/conda-forge" -c "$CondaMirror/pkgs/main" -c "$CondaMirror/pkgs/free"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    镜像 channel 创建失败, 回退官方 conda-forge 重试"
        conda create -y -n $EnvName "python=$PyVersion" --override-channels -c conda-forge
        if ($LASTEXITCODE -ne 0) {
            throw "创建 conda 环境失败, 请检查上面的 conda 报错信息。"
        }
    }
}

conda activate $EnvName
if ($env:CONDA_DEFAULT_ENV -ne $EnvName) {
    throw "激活环境 '$EnvName' 失败, 当前环境为 '$env:CONDA_DEFAULT_ENV'。请关闭窗口重开后重试。"
}
conda config --env --set subdir win-64 2>$null | Out-Null

$pyArch = python -c "import platform; print(platform.machine())" 2>$null
Write-Host "==> Python 架构: $pyArch (win-64 = AMD64, ARM64 上经系统模拟运行)"

function Invoke-PipInstall {
    param([string[]]$PipArgs)
    python -m pip install @PipArgs -i $PipIndex --trusted-host $PipHost
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    镜像源失败, 回退官方 PyPI 重试"
        python -m pip install @PipArgs
    }
}

Write-Host "==> 升级 pip (镜像: $PipIndex, 失败回退官方源)"
Invoke-PipInstall @("--upgrade", "pip")

Write-Host "==> 安装 requirements.txt 依赖 (镜像: $PipIndex, 失败回退官方源)"
Invoke-PipInstall @("-r", "requirements.txt")

Write-Host "==> 安装 playwright chromium (镜像: $PlaywrightDownloadHost, 失败回退官方源)"
$env:PLAYWRIGHT_DOWNLOAD_HOST = $PlaywrightDownloadHost
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "    镜像下载失败, 回退官方源重试"
    Remove-Item Env:\PLAYWRIGHT_DOWNLOAD_HOST -ErrorAction SilentlyContinue
    try { python -m playwright install chromium } catch { Write-Host "    playwright 安装失败, 继续" }
}

Write-Host "==> 解压表情包到 meme_generator 包目录"
python "$ScriptDir\_setup_memes.py" "$ProjectDir"

Write-Host "==> 安装字体 YurukaFangTang.ttf"
$fontSrc = Join-Path $ProjectDir "data\nonebot_plugin_meme_stickers\_shared\YurukaFangTang.ttf"
if (Test-Path $fontSrc) {
    $fontDst = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts\YurukaFangTang.ttf"
    $fontDstDir = Split-Path -Parent $fontDst
    if (-not (Test-Path $fontDstDir)) { New-Item -ItemType Directory -Force -Path $fontDstDir | Out-Null }
    Copy-Item -Path $fontSrc -Destination $fontDst -Force
    $regPath = "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    New-ItemProperty -Path $regPath -Name "YurukaFangTang (TrueType)" -Value $fontDst -PropertyType String -Force | Out-Null
    Write-Host "    字体已安装 (当前用户) 到 $fontDst"
} else {
    Write-Host "    未找到字体源文件, 跳过: $fontSrc"
}

Write-Host "==> 准备 .env.prod 配置文件 (交互式向导)"
$envProd = Join-Path $ProjectDir ".env.prod"
$setupEnv = Join-Path $ScriptDir "_setup_env.py"
try {
    & python $setupEnv $ProjectDir
} catch {
    Write-Host "    配置向导异常退出: $_"
}
if (-not (Test-Path $envProd)) {
    Copy-Item -Path (Join-Path $ProjectDir ".env.prod_example") -Destination $envProd -Force
    Write-Host "    已回退为直接复制示例文件, 启动前请手动编辑 .env.prod"
}

Write-Host "==> 准备自签名 SSL 证书 (bot.py 会加载 .\utils\ssl\)"
$sslDir = Join-Path $ProjectDir "utils\ssl"
$keyFile = Join-Path $sslDir "privkey.key"
$pemFile = Join-Path $sslDir "fullchain.pem"
if ((Test-Path $keyFile) -and (Test-Path $pemFile)) {
    Write-Host "    SSL 证书已存在, 保持不变"
} else {
    if (-not (Test-Path $sslDir)) { New-Item -ItemType Directory -Force -Path $sslDir | Out-Null }
    $opensslExe = "openssl"
    $condaOpenssl = Join-Path $env:CONDA_PREFIX "Library\bin\openssl.exe"
    if (Test-Path $condaOpenssl) { $opensslExe = $condaOpenssl }
    try {
        & $opensslExe req -x509 -newkey rsa:2048 -nodes -keyout $keyFile -out $pemFile -days 3650 -subj "/CN=airicore.local" 2>$null
    } catch {
        Write-Host "    未找到可用的 openssl。"
    }
    if ((Test-Path $keyFile) -and (Test-Path $pemFile) -and ((Get-Item $pemFile).Length -gt 0)) {
        Write-Host "    已在 $sslDir 生成自签名证书"
    } else {
        Write-Host "    警告: 证书生成失败! bot.py 需要 .\utils\ssl\privkey.key 与 .\utils\ssl\fullchain.pem,"
        Write-Host "    请手动提供, 或修改 bot.py 去掉 ssl_keyfile/ssl_certfile 参数, 否则无法启动。"
    }
}

Write-Host "==> 创建运行时目录"
foreach ($d in @("logs", "data")) {
    $p = Join-Path $ProjectDir $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}

Write-Host "==> 依赖自检"
$checkPy = Join-Path $env:TEMP "airicore_depcheck.py"
@'
import importlib.util
mods = ["nonebot", "meme_generator", "playwright", "aiohttp", "openai", "numpy", "PIL", "skia", "uvicorn", "psutil", "mcrcon"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print("    缺失模块: " + ", ".join(missing))
    raise SystemExit(1)
print("    核心依赖齐全")
'@ | Set-Content -Path $checkPy -Encoding UTF8
python $checkPy
if ($LASTEXITCODE -ne 0) {
    Write-Host "    警告: 依赖自检未通过, 请回看上面的 pip 报错。"
}
Remove-Item $checkPy -Force -ErrorAction SilentlyContinue

Write-Host "==> 整理启动脚本"
$srcBat = Join-Path $ProjectDir "launch_windows.bat"
$dstBat = Join-Path $ProjectDir "launch.bat"
if (Test-Path $srcBat) {
    Move-Item -Force -Path $srcBat -Destination $dstBat
    Write-Host "    launch_windows.bat -> launch.bat"
} elseif (Test-Path $dstBat) {
    Write-Host "    launch.bat 已存在, 跳过重命名"
} else {
    Write-Host "    警告: 未找到 launch_windows.bat 或 launch.bat"
}
foreach ($f in @("launch_linux.sh", "launch_macos.sh", "launch_macos.command", "launch.sh", "launch.command")) {
    $p = Join-Path $ProjectDir $f
    if (Test-Path $p) {
        Remove-Item -Force $p
        Write-Host "    已删除 $f"
    }
}

Write-Host ""
Write-Host "==> 部署完成。后续步骤:"
Write-Host "    1. 启动: launch.bat"
Write-Host "    2. 想改配置: 重跑向导 python 一键部署脚本\_setup_env.py"
Write-Host "       或直接编辑 .env.prod"

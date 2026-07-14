@echo off
chcp 65001 >nul
title AiriCore launcher (Windows)
setlocal enabledelayedexpansion

set "ENV_NAME=airicore"
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "LANG=en_US.UTF-8"

echo ==> AiriCore 一键启动 (Windows)
echo     项目目录: %PROJECT_DIR%

set "CONDA_BAT="
for %%D in (
    "%USERPROFILE%\miniconda3\condabin\conda.bat"
    "%USERPROFILE%\anaconda3\condabin\conda.bat"
    "C:\ProgramData\miniconda3\condabin\conda.bat"
    "C:\ProgramData\Anaconda3\condabin\conda.bat"
) do (
    if exist "%%~D" (
        set "CONDA_BAT=%%~D"
        goto :found_conda
    )
)

where conda >nul 2>nul
if %errorlevel%==0 (
    for /f "delims=" %%B in ('conda info --base 2^>nul') do set "CONDA_BASE=%%B"
    if exist "!CONDA_BASE!\condabin\conda.bat" set "CONDA_BAT=!CONDA_BASE!\condabin\conda.bat"
)

:found_conda
if not defined CONDA_BAT (
    echo 错误: 未检测到 conda, 请先运行部署脚本 一键部署脚本\deploy_windows.ps1
    pause
    exit /b 1
)

echo ==> 使用 conda: !CONDA_BAT!
call "!CONDA_BAT!" activate %ENV_NAME%
if %errorlevel% neq 0 (
    echo 错误: 无法激活环境 '%ENV_NAME%', 请先运行部署脚本
    pause
    exit /b 1
)

echo ==> 启动 AiriCore (崩溃后自动重启)
python airi.py
pause

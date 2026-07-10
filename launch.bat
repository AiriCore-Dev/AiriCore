@echo off
title AiriCore launcher (Windows)
cd /d "%~dp0"
chcp 65001 >nul
set LANG=en_US.UTF-8
call "%USERPROFILE%\miniconda3\condabin\conda.bat" activate airicore
python airi.py
pause
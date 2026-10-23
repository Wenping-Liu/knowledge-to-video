@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.12 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    py -3.12 scripts\setup.py --yes %*
    goto finish
  )
)
where python >nul 2>nul
if %errorlevel%==0 (
  python scripts\setup.py --yes %*
) else (
  echo 请先安装 Python 3.12：https://www.python.org/downloads/
)
:finish
pause

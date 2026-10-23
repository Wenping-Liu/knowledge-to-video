@echo off
chcp 65001 >nul
cd /d "%~dp0"
if defined KTV_PYTHON (
  "%KTV_PYTHON%" "可编辑工程\runtime\scripts\serve.py" --project "可编辑工程\工程数据.json" --open
  goto finish
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.12 "可编辑工程\runtime\scripts\serve.py" --project "可编辑工程\工程数据.json" --open
) else (
  python "可编辑工程\runtime\scripts\serve.py" --project "可编辑工程\工程数据.json" --open
)
:finish
if errorlevel 1 pause

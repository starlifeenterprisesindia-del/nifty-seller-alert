@echo off
setlocal
cd /d "%~dp0"
python apply_v50_7_fix.py .
if errorlevel 1 (
  echo.
  echo FIX FAILED. Your original files were not changed, or were restored from backup.
  pause
  exit /b 1
)
echo.
echo FIX COMPLETE. Upload the four changed Python files to GitHub.
pause

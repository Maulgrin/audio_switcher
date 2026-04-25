@echo off
cd /d %~dp0
setlocal ENABLEDELAYEDEXPANSION

REM Get date/time for commit message
for /f "tokens=1-5 delims=/: " %%d in ("%date% %time%") do (
    set msg=Auto update on %%d-%%e-%%f_%%g
)

git add .
git commit -m "!msg!"
git push
pause
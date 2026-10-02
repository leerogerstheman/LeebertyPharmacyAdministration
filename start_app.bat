@echo off
rem LeebertyPharmacyAdministration - 桌面应用启动（优先 exe，无 exe 时回退 pythonw）
cd /d %~dp0
if exist "%~dp0LeebertyPharmacyAdministration.exe" (
  start "" "%~dp0LeebertyPharmacyAdministration.exe"
) else (
  if exist "%~dp0dist\LeebertyPharmacyAdministration.exe" (
    start "" "%~dp0dist\LeebertyPharmacyAdministration.exe"
  ) else (
    start "" pythonw agent\gui.py
  )
)
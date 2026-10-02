@echo off
chcp 65001 >nul
rem 在桌面创建 LeebertyPharmacyAdministration 快捷方式
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\LeebertyPharmacyAdministration.lnk'); $s.TargetPath='%CD%\LeebertyPharmacyAdministration.exe'; $s.WorkingDirectory='%CD%'; $s.Description='药事管理智能 Agent'; $s.Save(); Write-Host 快捷方式已创建到桌面"
pause
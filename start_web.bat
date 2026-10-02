@echo off
chcp 65001 >nul
title LeebertyPharmacyAdministration - Web 服务
cd /d %~dp0
echo 正在启动药事管理 Agent Web 服务...
python agent\server.py --port 8901
pause

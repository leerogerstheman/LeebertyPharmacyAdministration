@echo off
chcp 65001 >nul
title LeebertyPharmacyAdministration - 命令行 Agent
cd /d %~dp0
echo 正在启动药事管理 Agent 命令行...
python agent\cli.py
pause

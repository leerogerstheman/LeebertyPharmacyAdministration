@echo off
rem LeebertyPharmacyAdministration - 桌面应用启动（无控制台窗口）
title LeebertyPharmacyAdministration
cd /d %~dp0
start "" pythonw agent\gui.py

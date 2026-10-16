@echo off
chcp 65001 >nul
title EazyMarket - preparation du paquet de deploiement
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe deploiement\faire_le_paquet.py
) else (
    python deploiement\faire_le_paquet.py
)
pause

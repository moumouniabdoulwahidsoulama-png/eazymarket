@echo off
chcp 65001 >nul
title EazyMarket - appliquer la mise a jour
cd /d "%~dp0"

set SOURCE=mise-a-jour-eazymarket

if not exist "%SOURCE%\" (
    echo.
    echo   Rien a appliquer : le dossier "%SOURCE%" est introuvable.
    echo   Extrayez d abord mise-a-jour-eazymarket.zip ici.
    echo.
    pause
    exit /b 1
)

echo.
echo   Copie des fichiers par-dessus le projet...
echo.
xcopy "%SOURCE%\*" "%~dp0" /E /Y /I
if errorlevel 1 (
    echo.
    echo   La copie a echoue. Rien n a ete supprime.
    pause
    exit /b 1
)

echo.
echo   Fichiers appliques. Nettoyage du dossier temporaire...
rd /s /q "%SOURCE%"
if exist "mise-a-jour-eazymarket.zip" del /q "mise-a-jour-eazymarket.zip"

echo.
echo   ================================================
echo   Mise a jour appliquee.
echo   ================================================
echo.
echo   Fabrication du paquet a envoyer sur le serveur...
echo.
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe deploiement\faire_le_paquet.py
) else (
    python deploiement\faire_le_paquet.py
)
pause

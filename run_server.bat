@echo off
chcp 65001 >nul
title EazyMarket - serveur de developpement
cd /d "%~dp0"

echo ==========================================
echo   EazyMarket - demarrage
echo ==========================================

if not exist "venv\Scripts\activate.bat" (
    echo [1/6] Creation de l'environnement virtuel...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo [2/6] Installation des dependances...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

if not exist ".env" (
    echo [3/6] Creation du fichier .env a partir de .env.example...
    copy .env.example .env >nul
    echo     ^> Ouvrez .env et renseignez votre numero Orange Money.
)

echo [4/6] Application des migrations...
python manage.py migrate

echo [5/6] Rayons de la boutique et metiers de l'annuaire...
python manage.py init_catalogue

echo [6/6] Lancement du serveur...
echo.
echo   Premiere utilisation ? Ouvrez une autre fenetre et lancez :
echo       venv\Scripts\activate ^&^& python manage.py createsuperuser
echo   pour creer votre compte administrateur.
echo.
echo   Ordinateur  : http://127.0.0.1:8000
echo   Telephone   : http://%COMPUTERNAME%:8000  (meme reseau Wi-Fi)
echo.
echo   Ctrl+C pour arreter.
echo.
python manage.py runserver 0.0.0.0:8000

pause

@echo off
title Server Manager Bot
cd /d "%~dp0"

echo ========================================
echo   Server Manager Bot - Запуск
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не установлен!
    echo Скачай Python с https://python.org
    echo При установке поставь галочку "Add Python to PATH"
    pause
    exit
)

:: Проверяем наличие venv
if exist "D:\works\.venv\Scripts\python.exe" (
    set PYTHON=D:\works\.venv\Scripts\python.exe
    echo Используется venv: D:\works\.venv
) else (
    set PYTHON=python
    echo Используется системный Python
)

echo.
echo Проверка зависимостей...
%PYTHON% -m pip install -r requirements.txt >nul 2>&1
echo Зависимости установлены!
echo.
echo Запуск бота...
echo.

%PYTHON% bot.py

echo.
echo Бот остановлен.
pause

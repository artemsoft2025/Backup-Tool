@echo off
REM ============================================================
REM Пример хука после создания архива (Windows)
REM Вызывается backup6.py после каждого успешно созданного архива.
REM
REM Аргументы:
REM   %1 — полный путь к архиву
REM   %2 — имя профиля
REM   %3 — тип: full или inc
REM   %4 — размер архива в байтах
REM
REM Переменные окружения (доступны всегда):
REM   BACKUP_FILE, BACKUP_PROFILE, BACKUP_TYPE, BACKUP_SIZE
REM ============================================================
setlocal enabledelayedexpansion

set "ARCHIVE=%~1"
if "%ARCHIVE%"=="" set "ARCHIVE=%BACKUP_FILE%"
set "PROFILE=%~2"
if "%PROFILE%"=="" set "PROFILE=%BACKUP_PROFILE%"
set "TYPE=%~3"
if "%TYPE%"=="" set "TYPE=%BACKUP_TYPE%"
set "SIZE=%~4"
if "%SIZE%"=="" set "SIZE=%BACKUP_SIZE%"

if not exist "%ARCHIVE%" (
    echo Архив не найден: %ARCHIVE% >&2
    exit /b 1
)

echo Хук: архив=%ARCHIVE% профиль=%PROFILE% тип=%TYPE% размер=%SIZE%

REM ============================================================
REM ВЫБЕРИТЕ ОДИН ИЗ ВАРИАНТОВ (раскомментируйте нужный блок)
REM ============================================================

REM --- Вариант A: копирование на сетевой диск / NAS ---
REM set "DEST=\\NAS\backups\%PROFILE%\%TYPE%"
REM if not exist "%DEST%" mkdir "%DEST%"
REM copy /Y "%ARCHIVE%" "%DEST%\"

REM --- Вариант B: rclone в облако ---
REM Сначала один раз: rclone config  (создать remote)
REM rclone copy "%ARCHIVE%" "yandex:Backups/%PROFILE%/%TYPE%/" --progress

REM --- Вариант C: scp (нужен OpenSSH или WinSCP) ---
REM scp "%ARCHIVE%" user@backup-server:/backups/%PROFILE%/%TYPE%/

REM --- Вариант D: уведомление в Telegram ---
REM set "TOKEN=ВАШ_ТОКЕН_БОТА"
REM set "CHAT_ID=ВАШ_CHAT_ID"
REM curl -s -X POST "https://api.telegram.org/bot%TOKEN%/sendMessage" -d "chat_id=%CHAT_ID%" -d "text=Бэкап %PROFILE%/%TYPE% готов: %ARCHIVE%" > nul

REM --- Вариант E (по умолчанию, безопасно): копирование в локальную папку ---
set "DEST_DIR=%USERPROFILE%\backup-upload\%PROFILE%\%TYPE%"
if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"
copy /Y "%ARCHIVE%" "%DEST_DIR%\" >nul
echo Скопировано в: %DEST_DIR%\%~nx1

exit /b 0

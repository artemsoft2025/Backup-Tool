#!/usr/bin/env bash
# ============================================================
# Пример хука после создания архива (Linux / macOS)
# Вызывается backup6.py после каждого успешно созданного архива.
#
# Аргументы:
#   $1 — полный путь к архиву
#   $2 — имя профиля
#   $3 — тип: full или inc
#   $4 — размер архива в байтах
#
# Переменные окружения (доступны всегда):
#   BACKUP_FILE, BACKUP_PROFILE, BACKUP_TYPE, BACKUP_SIZE
# ============================================================
set -u

ARCHIVE="${1:-${BACKUP_FILE:-}}"
PROFILE="${2:-${BACKUP_PROFILE:-}}"
TYPE="${3:-${BACKUP_TYPE:-}}"
SIZE="${4:-${BACKUP_SIZE:-0}}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
    echo "Архив не найден: $ARCHIVE" >&2
    exit 1
fi

echo "Хук: архив=$ARCHIVE профиль=$PROFILE тип=$TYPE размер=$SIZE"

# ============================================================
# ВЫБЕРИТЕ ОДИН ИЗ ВАРИАНТОВ (раскомментируйте нужный блок)
# ============================================================

# --- Вариант A: rsync на SSH-сервер ---
# SSH-ключ должен быть настроен: ssh-keygen && ssh-copy-id user@backup-server
# REMOTE="backup-server:/srv/backups/$PROFILE/$TYPE/"
# rsync -az --timeout=120 "$ARCHIVE" "$REMOTE"

# --- Вариант B: rclone в облако (Яндекс.Диск / Dropbox / S3 / ...) ---
# Сначала один раз: rclone config  (создать remote, например 'yandex')
# rclone copy "$ARCHIVE" "yandex:Backups/$PROFILE/$TYPE/" --progress

# --- Вариант C: scp ---
# scp -P 22 "$ARCHIVE" user@backup-server:/backups/$PROFILE/$TYPE/

# --- Вариант D: уведомление в Telegram ---
# TOKEN="ВАШ_ТОКЕН_БОТА"
# CHAT_ID="ВАШ_CHAT_ID"
# curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
#   -d "chat_id=$CHAT_ID" \
#   -d "text=✅ Бэкап $PROFILE/$TYPE готов: $(basename "$ARCHIVE") ($SIZE байт)" \
#   > /dev/null

# --- Вариант E (по умолчанию, безопасно): копирование в локальную папку ---
# Удобно для первого теста. Замените путь на свой.
DEST_DIR="$HOME/backup-upload/$PROFILE/$TYPE"
mkdir -p "$DEST_DIR"
cp "$ARCHIVE" "$DEST_DIR/"
echo "Скопировано в: $DEST_DIR/$(basename "$ARCHIVE")"

exit 0

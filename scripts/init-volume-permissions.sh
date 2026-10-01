#!/bin/sh
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
PROJECT_DIR="${1:-$(pwd)}"

case "$PROJECT_DIR" in
  /|"")
    echo "Refusing to operate on an unsafe project directory: $PROJECT_DIR" >&2
    exit 1
    ;;
esac

for relative_dir in data session downloads backups logs/backend logs/worker logs/frontend; do
  target="$PROJECT_DIR/$relative_dir"
  mkdir -p "$target"
done

chown -R "$PUID:$PGID" \
  "$PROJECT_DIR/data" \
  "$PROJECT_DIR/session" \
  "$PROJECT_DIR/downloads" \
  "$PROJECT_DIR/backups" \
  "$PROJECT_DIR/logs/backend" \
  "$PROJECT_DIR/logs/worker"

# nginx-unprivileged uses UID/GID 101 in the frontend runtime image.
chown -R 101:101 "$PROJECT_DIR/logs/frontend"

echo "Volume ownership initialized for PUID=$PUID PGID=$PGID"

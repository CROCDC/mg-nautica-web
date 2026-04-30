#!/bin/sh
set -e

# Sync baked-in uploads to the mounted volume without overwriting existing files.
# This ensures photos from the latest scrape are available even on an existing volume.
if [ -d /app/uploads_baked ] && [ "$(ls -A /app/uploads_baked 2>/dev/null)" ]; then
    count=$(find /app/uploads_baked -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "Syncing $count baked uploads to volume..."
    find /app/uploads_baked -mindepth 1 -type d | while read dir; do
        target="/app/uploads/${dir#/app/uploads_baked/}"
        mkdir -p "$target"
    done
    find /app/uploads_baked -type f | while read src; do
        dest="/app/uploads/${src#/app/uploads_baked/}"
        if [ ! -f "$dest" ]; then
            cp "$src" "$dest"
        fi
    done
fi

exec "$@"

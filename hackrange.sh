#!/bin/bash
# HackRange launcher — builds/starts everything and opens the browser.

echo "Starting HackRange..."
docker compose up -d --build

echo "Waiting for backend to be ready..."
sleep 4

URL="http://localhost:8080"

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"        # Linux
elif command -v open >/dev/null 2>&1; then
    open "$URL"             # macOS
else
    echo "Open this URL in your browser: $URL"
fi

echo ""
echo "HackRange is running at $URL"
echo "To stop it, run: docker compose down"

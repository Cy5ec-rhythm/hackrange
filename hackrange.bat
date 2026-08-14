@echo off
REM HackRange launcher — builds/starts everything and opens the browser.

echo Starting HackRange...
docker compose up -d --build

echo Waiting for backend to be ready...
timeout /t 4 /nobreak >nul

start http://localhost:8080

echo.
echo HackRange is running at http://localhost:8080
echo To stop it, run: docker compose down

@echo off
title Diefert Scanner v5 (con watchdog)
cd /d "F:\clude\diefert_scanner_v5"
echo ============================================
echo   Diefert Scanner v5 - iniciando con watchdog
echo   Si el scanner se cuelga, se reiniciara solo.
echo   Para detenerlo del todo: cierra esta ventana
echo   o presiona Ctrl+C.
echo ============================================
echo.
python watchdog.py

echo.
echo El watchdog se detuvo. Presiona una tecla para cerrar.
pause >nul

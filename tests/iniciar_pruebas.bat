@echo off
setlocal
title Pruebas - Gestion Estudio Contable

rem ===================================================================
rem  CORRE LAS 1282 PRUEBAS CONTRA LA BASE DE PRUEBAS.
rem
rem  Este es el launcher de las pruebas. El otro (iniciar.bat) es el del
rem  programa de verdad, y NO hay que confundirlo con este.
rem
rem  Que las pruebas corran contra `gestion_contable_test` y no contra la del
rem  estudio es lo IMPORTANTE: si una prueba escribe mal, escribe en la base de
rem  pruebas. El 02/10/2026 una suite borro asientos reales del estudio
rem  (ver AGENTE.md %6 bis) y no habia forma de recuperarlos.
rem
rem  Para USAR el programa de verdad, doble clic en iniciar.bat.
rem ===================================================================

cd /d "%~dp0"
set "RAIZ=%~dp0"
set "API=http://127.0.0.1:8011"

echo.
echo   PRUEBAS DEL SISTEMA
echo   ===================
echo.
echo   Base de datos: gestion_contable_test  (la del estudio NO se toca)
echo.

rem --- ¿La base de pruebas existe? ------------------------------------
python -X utf8 preparar_base_prueba.py >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] No se pudo preparar la base de pruebas.
    echo   Fijate si MySQL esta prendido y si el .env existe.
    echo.
    pause
    goto salir
)
echo   [OK] Base de pruebas lista.

rem --- ¿La API de pruebas ya esta? ------------------------------------
call :puertoLibre 8011
if errorlevel 1 (
    echo   [OK] La API de pruebas ya estaba encendida.
) else (
    echo   Encendiendo la API de pruebas ^(puerto 8011^)...
    rem DB_NAME va en el entorno de ESTE proceso, no en el .env: asi la API de
    %REM% pruebas nunca toca la base real, ni por accidente.
    start "Pruebas - API" /min /D "%RAIZ%..\backend" cmd /c "set DB_NAME=gestion_contable_test && python -m uvicorn app.main:app --host=127.0.0.1 --port=8011"
)

echo   Esperando a que la API responda...
call :esperar "%API%/health" 45
if errorlevel 1 (
    echo.
    echo   [ERROR] La API de pruebas no respondio.
    echo.
    pause
    goto salir
)
echo   [OK] API de pruebas andando.

rem --- Las pruebas ----------------------------------------------------
echo.
echo   Corriendo las pruebas contra la base de PRUEBAS...
echo   ------------------------------------------------------------------
set "GC_BASE_URL=%API%"
python -X utf8 correr_todas.py
set "RESULTADO=%errorlevel%"

echo   ------------------------------------------------------------------
echo.
if "%RESULTADO%"=="0" (
    echo   TODO EN VERDE. La base del estudio no se toco.
) else (
    echo   Hubo fallos. MIRA ARRIBA cual.
    echo.
    echo   Si el fallo es "no perdio datos reales", eso es lo que hace
    echo   correr las pruebas aparte: nunca deberia pasar.
)
echo.
pause
goto salir

rem --- Rutinas ----------------------------------------------------------
:puertoLibre
netstat -ano | findstr ":%1" | findstr "LISTENING" >nul
if %errorlevel%==0 exit /b 1
exit /b 0

:esperar
set "URL_=%~1"
set /a INTENTOS=%2
set /a I=0
:loop
curl -s -o nul -w "%%{http_code}" --max-time 2 "%URL_%" 2>nul | findstr /R "^[23]" >nul
if not errorlevel 1 exit /b 0
set /a I+=1
if %I% gte %INTENTOS% exit /b 1
timeout /t 1 >nul
goto loop

:salir
endlocal
exit /b 0
@echo off
setlocal
title Gestion Estudio Contable

rem ===================================================================
rem  ARRANCA EL SISTEMA: base de datos + web, y abre el navegador.
rem
rem  Se hace doble clic en este archivo y no hay que hacer nada mas.
rem  Para CERRAR: veni a esta ventana y presioná una tecla.
rem ===================================================================

cd /d "%~dp0"

set "RAIZ=%~dp0"
set "URL=http://localhost:4173"
set "API=http://127.0.0.1:8010"

echo.
echo   GESTION ESTUDIO CONTABLE
echo   ========================
echo.

rem --- ¿Están prendidos los servidores? --------------------------------
rem Si el usuario abre el acceso dos veces, NO hay que arrancar una segunda
rem copia: si el puerto ya está ocupado, se usa el que ya está corriendo.

call :puertoLibre 8010
if errorlevel 1 (
    echo   [OK] Base de datos ya estaba encendida.
) else (
    echo   Encendiendo la base de datos...
    rem `/D` cambia de carpeta SIN comillas anidadas. Con `cmd /c "cd /d "..."
    rem Windows mezcla las comillas y el comando queda partido: el servidor
    %REM% no arranca nunca y parece que el programa anda igual.
    start "Gestion - Base de datos" /min /D "%RAIZ%backend" python -m uvicorn app.main:app --host=127.0.0.1 --port=8010
)

call :puertoLibre 4173
if errorlevel 1 (
    echo   [OK] La pagina ya estaba encendida.
) else (
    echo   Encendiendo la pagina...
    rem El preview sirve `dist`: la version ya compilada. Es la que se usa
    rem todos los dias. Si se toco codigo hay que compilar antes
    rem (doble clic en build_frontend.bat).
    rem `npm` es un .cmd, por eso va con `cmd /c`; la carpeta la pone `/D`.
    start "Gestion - Pagina" /min /D "%RAIZ%frontend" cmd /c npm run preview
)

rem --- Esperar a que respondan ------------------------------------------
echo   Esperando a que todo esté listo...

call :esperar "%API%/health" 40
if errorlevel 1 goto fallo_api

call :esperar "%URL%" 40
if errorlevel 1 goto fallo_web

echo.
echo   [LISTO] Abriendo el navegador...
start "" "%URL%"

echo.
echo   ====================================================
echo    El sistema esta funcionando.
echo    Para CERRARLO: veni a esta ventana y presiona
echo    una tecla. Se apagan los dos servidores juntos.
echo   ====================================================
echo.

pause >nul
goto apagar

rem --- Errores ----------------------------------------------------------
:fallo_api
echo.
echo   [ERROR] La base de datos no respondio.
echo   Revisa que MySQL este prendido y que el archivo .env exista.
echo.
pause
goto salir

:fallo_web
echo.
echo   [ERROR] La pagina no respondio.
echo   Probable que falte compilar: doble clic en build_frontend.bat
echo   y volve a probar este archivo.
echo.
pause
goto salir

rem --- Apagar -----------------------------------------------------------
:apagar
echo.
echo   Apagando...

rem Se buscan los procesos POR PUERTO, no por nombre: el PWD de python y de
rem node son de otros programas y matarlos a ellos seria un lío. Con el
rem puerto se sabe exactamente cuál es el nuestro.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8010" ^| findstr "LISTENING"') do (
    echo   Cerrando la base de datos...
    taskkill /PID %%p /T /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat ":4173" ^| findstr "LISTENING"') do (
    echo   Cerrando la pagina...
    taskkill /PID %%p /T /F >nul 2>&1
)

echo.
echo   Apagado. Chau!
timeout /t 2 >nul
goto salir

rem --- Rutinas ----------------------------------------------------------

rem Devuelve errorlevel 1 si el puerto ESTA ocupado.
:puertoLibre
netstat -ano | findstr ":%1" | findstr "LISTENING" | findstr /R "127\.0\.0\.1\|0\.0\.0\.0" >nul
if %errorlevel%==0 exit /b 1
exit /b 0

rem Espera a que una URL responda. %2 = cantidad de intentos.
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
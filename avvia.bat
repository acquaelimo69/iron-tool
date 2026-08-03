@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo   Real Estate Investment Analyzer
echo ================================================
echo.

REM ================================================================
REM  STEP 1 - Trova Python
REM  Priorita: py launcher ^> PATH ^> cartelle comuni ^> registry
REM ================================================================

set "PYTHON_CMD="

REM --- 1a. Python Launcher (py -3) ---
py -3 -c "" >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)"') do set "PYTHON_CMD=%%i"
)
if defined PYTHON_CMD goto :found_python

REM --- 1b. python / python3 in PATH ---
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where python') do set "PYTHON_CMD=%%i"
)
if defined PYTHON_CMD goto :found_python

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where python3') do set "PYTHON_CMD=%%i"
)
if defined PYTHON_CMD goto :found_python

REM --- 1c. Scansione cartelle comuni ---
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" goto :set_313
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto :set_312
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" goto :set_311
if exist "C:\Python313\python.exe" goto :set_c313
if exist "C:\Python312\python.exe" goto :set_c312
if exist "C:\Python311\python.exe" goto :set_c311
if exist "C:\Program Files\Python313\python.exe" goto :set_pf313
if exist "C:\Program Files\Python312\python.exe" goto :set_pf312
if exist "C:\Program Files\Python311\python.exe" goto :set_pf311
if exist "C:\Program Files (x86)\Python313\python.exe" goto :set_pfx313
if exist "C:\Program Files (x86)\Python312\python.exe" goto :set_pfx312
if exist "C:\Program Files (x86)\Python311\python.exe" goto :set_pfx311
goto :try_registry

:set_313
set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
goto :found_python
:set_312
set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
goto :found_python
:set_311
set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
goto :found_python
:set_c313
set "PYTHON_CMD=C:\Python313\python.exe"
goto :found_python
:set_c312
set "PYTHON_CMD=C:\Python312\python.exe"
goto :found_python
:set_c311
set "PYTHON_CMD=C:\Python311\python.exe"
goto :found_python
:set_pf313
set "PYTHON_CMD=C:\Program Files\Python313\python.exe"
goto :found_python
:set_pf312
set "PYTHON_CMD=C:\Program Files\Python312\python.exe"
goto :found_python
:set_pf311
set "PYTHON_CMD=C:\Program Files\Python311\python.exe"
goto :found_python
:set_pfx313
set "PYTHON_CMD=C:\Program Files (x86)\Python313\python.exe"
goto :found_python
:set_pfx312
set "PYTHON_CMD=C:\Program Files (x86)\Python312\python.exe"
goto :found_python
:set_pfx311
set "PYTHON_CMD=C:\Program Files (x86)\Python311\python.exe"
goto :found_python

:try_registry
REM --- 1d. Registry HKCU ---
for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do set "PYTHON_CMD=%%b"
if defined PYTHON_CMD goto :found_python

REM --- 1e. Registry HKLM ---
for /f "tokens=2*" %%a in ('reg query "HKLM\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do set "PYTHON_CMD=%%b"
if defined PYTHON_CMD goto :found_python

REM ================================================================
REM  STEP 2 - Python non trovato: installazione automatica
REM ================================================================
echo.
echo Python non trovato sul sistema.
echo Installazione automatica di Python 3.12...
echo (al primo avvio potrebbe volerci qualche minuto)
echo.

REM --- 2a. Prova winget ---
where winget >nul 2>&1
if %errorlevel% equ 0 (
    echo Installazione tramite winget...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent >nul 2>&1
    if %errorlevel% equ 0 goto :post_install
    echo winget non riuscito, provo il download diretto...
)

REM --- 2b. Download diretto da python.org ---
set "INSTALLER=%TEMP%\python-3.12.10-amd64.exe"

echo Download Python 3.12 da python.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe', '%INSTALLER%')" >nul 2>&1

if not exist "%INSTALLER%" (
    echo.
    echo =============================================
    echo  ERRORE: impossibile scaricare Python.
    echo =============================================
    echo.
    echo Installa manualmente Python 3.12 da:
    echo   https://www.python.org/downloads/
    echo.
    echo Dopo l'installazione, riavvia questo script.
    echo.
    pause
    exit /b 1
)

echo Installazione silenziosa di Python 3.12...
start /wait "" "%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1
del "%INSTALLER%" >nul 2>&1

:post_install

REM ================================================================
REM  STEP 3 - Ricerca post-installazione
REM ================================================================
set "PYTHON_CMD="

py -3 -c "" >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)"') do set "PYTHON_CMD=%%i"
)
if defined PYTHON_CMD goto :found_python

where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where python') do set "PYTHON_CMD=%%i"
)
if defined PYTHON_CMD goto :found_python

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :found_python
)

echo.
echo Python e' stato installato ma non e' stato trovato.
echo Chiudi questa finestra e riapri il file avvia.bat.
echo.
pause
exit /b 1

REM ================================================================
REM  STEP 4 - Verifica versione e avvio
REM ================================================================

:found_python
echo Python trovato: "%PYTHON_CMD%"
"%PYTHON_CMD%" --version
echo.

REM Controllo versione minima (3.11+)
"%PYTHON_CMD%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if %errorlevel% neq 0 (
    echo.
    echo =============================================
    echo  ATTENZIONE: Python troppo vecchio.
    echo =============================================
    echo.
    echo Servono Python 3.11, 3.12 o 3.13.
    echo Installa Python 3.12 da:
    echo   https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM --- Creazione venv (solo al primo avvio) ---
if not exist ".venv" (
    echo Primo avvio: creazione ambiente virtuale...
    "%PYTHON_CMD%" -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo ERRORE: impossibile creare l'ambiente virtuale.
        echo.
        pause
        exit /b 1
    )

    echo Aggiornamento pip...
    .venv\Scripts\python.exe -m pip install -q --upgrade pip >nul 2>&1

    echo Installazione dipendenze (1-2 minuti^)...
    .venv\Scripts\python.exe -m pip install -q --prefer-binary -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo =============================================
        echo  ERRORE installazione dipendenze.
        echo =============================================
        echo.
        echo Riprova dopo aver installato Python 3.12 da:
        echo   https://www.python.org/downloads/
        echo.
        echo Dopo aver risolto, cancella la cartella .venv e riesegui.
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Installazione completata!
    echo.
)

REM ================================================================
REM  STEP 5 - Avvio applicazione
REM ================================================================

echo ================================================
echo  Applicazione in avvio...
echo  Apri il browser su:  http://localhost:8501
echo  Per chiudere: Ctrl+C in questa finestra
echo ================================================
echo.

.venv\Scripts\streamlit run app.py

pause

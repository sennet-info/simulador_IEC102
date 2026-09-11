@echo off
setlocal

set "VENV_PYTHON=.venv\Scripts\python.exe"

if not exist .venv (
    python -m venv .venv
)

if not exist "%VENV_PYTHON%" (
    echo No se encontro %VENV_PYTHON%. Vuelve a crear el entorno con: python -m venv .venv
    exit /b 1
)

echo Using interpreter: %VENV_PYTHON%
"%VENV_PYTHON%" --version
"%VENV_PYTHON%" -m pip install --upgrade pip==26.0.1
"%VENV_PYTHON%" -m pip install -r requirements.txt pyinstaller
"%VENV_PYTHON%" -m PyInstaller --name IEC102MeterSimulator --onefile --windowed src\main.py

endlocal

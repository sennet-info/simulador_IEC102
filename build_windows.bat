@echo off
setlocal
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --name IEC102MeterSimulator --onefile --windowed src\main.py
endlocal

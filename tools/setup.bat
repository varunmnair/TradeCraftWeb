@echo off
echo Setting up TradeCraftX Environment...

cd /D "%~dp0\.."

if not exist venv (
    python -m venv venv
    echo Virtual environment created.
)

call venv\Scripts\activate
pip install -r requirements.txt
echo Setup complete. You can now run 'tools\run.bat'.
pause

@echo off
REM One-click setup for a new Windows computer: makes a private Python
REM environment, installs everything the website needs, and runs the tests.
REM Needs Python 3 installed (https://www.python.org, tick "Add Python to PATH").
cd /d "%~dp0"
python -m venv venv || goto :fail
call venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :fail
pip install pyserial || goto :fail
echo.
echo Running the tests...
python run_tests.py
echo.
echo Done. To start the website on this computer:
echo     venv\Scripts\activate
echo     python app.py
echo then open http://localhost:5000
goto :eof
:fail
echo.
echo Setup stopped because a step failed. Read the message above it.
exit /b 1

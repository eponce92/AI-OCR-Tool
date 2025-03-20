@echo off
echo Starting AI-OCR Tool...

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the Flask application
echo Starting Flask application...
python run.py

pause 
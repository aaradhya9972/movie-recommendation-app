@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install project dependencies. Check that Python and pip are installed.
  pause
  exit /b 1
)
if not exist data\ratings.csv (
  python backend\generate_dataset.py
  if errorlevel 1 (
    echo Failed to generate the movie dataset.
    pause
    exit /b 1
  )
)
if not exist artifacts\model.pkl (
  python backend\train.py
  if errorlevel 1 (
    echo Failed to train the recommendation model.
    pause
    exit /b 1
  )
)
python backend\app.py
if errorlevel 1 (
  echo CineMatch backend stopped with an error.
  pause
  exit /b 1
)

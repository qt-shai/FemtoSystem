@echo off

REM Specify the path to your PackagesList.txt file
set REQUIREMENTS_FILE=PackagesList.txt

REM Check if the PackagesList file exists
if not exist %REQUIREMENTS_FILE% (
    echo Error: PackagesList.txt file not found!
    exit /b 1
)

REM Install packages using pip
pip install -r %REQUIREMENTS_FILE%

REM Upgrade pip
python.exe -m pip install --upgrade pip

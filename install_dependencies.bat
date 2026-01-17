@echo off
REM Batch script to install dependencies on Windows
echo ================================================================================
echo Installing dependencies for Cornels Cryptobot...
echo ================================================================================
echo.

REM Check Python version
python --version
python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ================================================================================
    echo ERROR: Python 3.9 or higher is required!
    echo ================================================================================
    echo.
    echo py-clob-client requires Python 3.9+
    echo Please upgrade Python from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

python -m pip install --upgrade pip setuptools wheel
echo.

echo Installing core dependencies...
python -m pip install python-dotenv>=1.0.0
python -m pip install httpx
python -m pip install eth-account>=0.13.0
python -m pip install eth-utils>=4.1.1
echo.

echo Installing py-clob-client...
python -m pip install py-clob-client>=0.34.5
if %ERRORLEVEL% NEQ 0 (
    echo PyPI installation failed, trying GitHub...
    python -m pip install git+https://github.com/Polymarket/py-clob-client.git
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo ================================================================================
        echo ERROR: Failed to install py-clob-client
        echo ================================================================================
        echo.
        echo This may be due to:
        echo   - Missing Visual Studio Build Tools
        echo   - Network issues
        echo   - Missing dependencies
        echo.
        echo Try installing manually:
        echo   pip install git+https://github.com/Polymarket/py-clob-client.git
        echo.
        pause
        exit /b 1
    )
)
echo.

echo Installing optional dependencies...
python -m pip install python-telegram-bot>=20.0
python -m pip install pytz>=2023.3
echo.

echo ================================================================================
echo Installation completed!
echo ================================================================================
echo.
echo Next steps:
echo 1. Copy 'env.template' to '.env' and fill in your credentials
echo 2. Run: python Cornels_Cryptobot.py
echo.

pause

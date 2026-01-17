#!/usr/bin/env python
"""
Setup script to install all dependencies for Cornels Cryptobot.
Run this script to ensure all required packages are installed.
"""

import subprocess
import sys
import os

def check_python_version():
    """Check if Python version is 3.9 or higher."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("=" * 80)
        print("ERROR: Python 3.9 or higher is required!")
        print("=" * 80)
        print(f"Current Python version: {version.major}.{version.minor}.{version.micro}")
        print("")
        print("py-clob-client requires Python 3.9+")
        print("")
        print("Please upgrade Python:")
        print("  - Download from: https://www.python.org/downloads/")
        print("  - Or use pyenv: https://github.com/pyenv/pyenv")
        print("")
        return False
    return True

def install_requirements():
    """Install packages from requirements.txt"""
    # Check Python version first
    if not check_python_version():
        return False
    
    requirements_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    
    if not os.path.exists(requirements_file):
        print(f"Error: {requirements_file} not found!")
        return False
    
    print("=" * 80)
    print("Installing dependencies for Cornels Cryptobot...")
    print("=" * 80)
    print("")
    
    # Upgrade pip, setuptools, and wheel first
    print("Upgrading pip, setuptools, and wheel...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print("  OK: pip tools upgraded")
    except subprocess.CalledProcessError:
        print("  WARNING: Failed to upgrade pip tools")
    
    # Install core dependencies first
    print("Installing core dependencies...")
    core_deps = ["python-dotenv>=1.0.0", "httpx", "eth-account>=0.13.0", "eth-utils>=4.1.1"]
    for dep in core_deps:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            print(f"  OK: {dep.split('>=')[0]} installed")
        except subprocess.CalledProcessError:
            print(f"  WARNING: Failed to install {dep}")
    
    # Try to install py-clob-client from PyPI first
    print("Installing py-clob-client...")
    success = False
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "py-clob-client>=0.34.5"],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("  OK: py-clob-client installed from PyPI")
            success = True
        else:
            raise subprocess.CalledProcessError(result.returncode, "pip install")
    except (subprocess.CalledProcessError, Exception):
        # If PyPI fails, try GitHub
        print("  PyPI installation failed, trying GitHub...")
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "install", 
                                   "git+https://github.com/Polymarket/py-clob-client.git"],
                                  capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("  OK: py-clob-client installed from GitHub")
                success = True
            else:
                print(f"  Error output: {result.stderr[:200]}")
                raise subprocess.CalledProcessError(result.returncode, "pip install")
        except subprocess.CalledProcessError as e:
            print("  ERROR: Failed to install py-clob-client")
            print("  This may be due to:")
            print("    - Missing build tools (Visual Studio Build Tools on Windows)")
            print("    - Network issues")
            print("    - Missing dependencies")
            print("")
            print("  Try installing manually:")
            print("    pip install git+https://github.com/Polymarket/py-clob-client.git")
            print("")
            print("  Or install dependencies individually:")
            print("    pip install httpx eth-account eth-utils python-dotenv")
            print("    pip install git+https://github.com/Polymarket/py-clob-client.git")
            return False
    
    if not success:
        return False
    
    # Install optional dependencies
    print("Installing optional dependencies...")
    optional_packages = [
        "python-telegram-bot>=20.0",
        "pytz>=2023.3"
    ]
    
    for package in optional_packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            print(f"  OK: {package.split('>=')[0]} installed")
        except subprocess.CalledProcessError:
            print(f"  WARNING: Failed to install {package.split('>=')[0]} (optional)")
    
    print("")
    print("=" * 80)
    print("SUCCESS: Dependencies installation completed!")
    print("=" * 80)
    print("")
    print("Next steps:")
    print("1. Copy 'env.template' to '.env' and fill in your credentials")
    print("2. Run: python Cornels_Cryptobot.py")
    return True

if __name__ == "__main__":
    success = install_requirements()
    sys.exit(0 if success else 1)

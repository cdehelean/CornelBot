# Installation Guide

## Important: Python Version Requirement

**py-clob-client requires Python 3.9 or higher!**

If you have Python 3.8 or lower, you must upgrade before installing dependencies.

### Check Your Python Version

```bash
python --version
```

If it shows Python 3.8.x or lower, you need to upgrade.

### Upgrade Python

1. **Download Python 3.9+** from: https://www.python.org/downloads/
2. **Install** the new version
3. **Verify** installation: `python --version` should show 3.9 or higher

## Installation Methods

### Method 1: Automated Installation (Recommended)

**Windows:**
- Double-click `install_dependencies.bat`

**Linux/Mac:**
```bash
bash install_dependencies.sh
```

**Or use Python script:**
```bash
python setup.py
```

### Method 2: Manual Installation

1. **Upgrade pip tools:**
   ```bash
   python -m pip install --upgrade pip setuptools wheel
   ```

2. **Install core dependencies:**
   ```bash
   pip install python-dotenv httpx eth-account eth-utils
   ```

3. **Install py-clob-client:**
   
   **Try PyPI first:**
   ```bash
   pip install py-clob-client
   ```
   
   **If that fails, install from GitHub:**
   ```bash
   pip install git+https://github.com/Polymarket/py-clob-client.git
   ```

4. **Install optional dependencies:**
   ```bash
   pip install python-telegram-bot pytz
   ```

### Method 3: Using requirements.txt

```bash
pip install -r requirements.txt
```

If `py-clob-client` fails, try installing from GitHub:
```bash
pip install git+https://github.com/Polymarket/py-clob-client.git
```

## Troubleshooting

### Error: "No matching distribution found for py-clob-client"

**Solution:** Install from GitHub instead:
```bash
pip install git+https://github.com/Polymarket/py-clob-client.git
```

### Error: "Failed building wheel for pysha3"

**Cause:** Missing build tools or incompatible Python version.

**Solutions:**
1. **Upgrade Python** to 3.9 or higher (required)
2. **Install Visual Studio Build Tools** (Windows):
   - Download: https://visualstudio.microsoft.com/downloads/
   - Install "Desktop Development with C++" workload
3. **On Linux**, install build essentials:
   ```bash
   sudo apt-get install build-essential python3-dev
   ```

### Error: "poly-eip712-structs not found"

**Solution:** This dependency is included when installing py-clob-client from GitHub. Make sure you're installing from GitHub if PyPI fails.

### Error: "Python version too low"

**Solution:** You must upgrade to Python 3.9 or higher. py-clob-client does not support Python 3.8 or lower.

## Verify Installation

After installation, verify it works:

```python
python -c "from py_clob_client.client import ClobClient; print('OK')"
```

If you see "OK", the installation was successful!

## Next Steps

1. Copy `env.template` to `.env`
2. Fill in your credentials in `.env`
3. Run: `python Cornels_Cryptobot.py`

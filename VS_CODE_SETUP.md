# VS Code Python Interpreter Setup

If you're getting `ModuleNotFoundError` in VS Code's Python Debug Console, it's likely using a different Python interpreter than your terminal.

## How to Fix

### 1. Select the Correct Python Interpreter

1. **Open Command Palette:**
   - Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)

2. **Select Interpreter:**
   - Type: `Python: Select Interpreter`
   - Choose the interpreter that has your packages installed
   - Usually: `C:\Program Files\Python38\python.exe` (or your Python 3.9+ path)

### 2. Verify the Interpreter

Run this in VS Code's terminal (not Debug Console):
```bash
python verify_dependencies.py
```

This will show which Python interpreter is being used and if all packages are installed.

### 3. Install Packages in the Correct Environment

If packages are missing, install them using the same Python interpreter:
```bash
python -m pip install -r requirements.txt
```

### 4. Alternative: Use VS Code Terminal Instead of Debug Console

The Debug Console sometimes has issues with imports. Try running your script in the integrated terminal instead:

1. Open terminal: `Ctrl+`` (backtick) or `Terminal > New Terminal`
2. Run: `python native_split_test.py`

### 5. Check Your `.vscode/settings.json`

You can also explicitly set the Python path in your workspace settings:

```json
{
    "python.defaultInterpreterPath": "C:\\Program Files\\Python38\\python.exe"
}
```

Replace with your actual Python path.

## Quick Test

Run this in VS Code's terminal to verify:
```python
python -c "from dotenv import load_dotenv; print('OK')"
```

If this works in the terminal but not in Debug Console, it's an interpreter selection issue.

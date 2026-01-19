"""
Quick script to verify all dependencies are installed correctly.
Run this to check if your Python environment has all required packages.
"""

import sys

print("=" * 80)
print("Checking Python Environment and Dependencies")
print("=" * 80)
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print()

# Check required packages
required_packages = {
    'dotenv': 'python-dotenv',
    'web3': 'web3',
    'eth_account': 'eth-account',
    'eth_utils': 'eth-utils',
}

missing = []
installed = []

for module_name, package_name in required_packages.items():
    try:
        __import__(module_name)
        installed.append(f"[OK] {package_name}")
        print(f"[OK] {package_name}")
    except ImportError as e:
        missing.append(f"[MISSING] {package_name}")
        print(f"[MISSING] {package_name}")
        print(f"  Error: {e}")

print()
print("=" * 80)
if missing:
    print("[ERROR] Some dependencies are missing!")
    print()
    print("Install missing packages with:")
    print("  pip install -r requirements.txt")
    print()
    print("Or install individually:")
    for item in missing:
        pkg = item.replace("[MISSING] ", "")
        print(f"  pip install {pkg}")
    sys.exit(1)
else:
    print("[SUCCESS] All dependencies are installed!")
    print()
    print("You can now run:")
    print("  python native_split_test.py")
    sys.exit(0)

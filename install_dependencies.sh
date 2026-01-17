#!/bin/bash
# Shell script to install dependencies on Linux/Mac

echo "================================================================================"
echo "Installing dependencies for Cornels Cryptobot..."
echo "================================================================================"
echo ""

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo "✅ All dependencies installed successfully!"
    echo "================================================================================"
    echo ""
    echo "Next steps:"
    echo "1. Copy 'env.template' to '.env' and fill in your credentials"
    echo "2. Run: python3 Cornels_Cryptobot.py"
else
    echo ""
    echo "================================================================================"
    echo "❌ Error installing dependencies!"
    echo "================================================================================"
    echo ""
    echo "Try running manually:"
    echo "  pip3 install -r requirements.txt"
fi

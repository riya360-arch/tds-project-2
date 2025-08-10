#!/bin/bash

# ================= INSTRUCTIONS =================
echo "=============================================="
echo " How to get the required credentials:"
echo ""
echo " 1. Get your Google API key here:"
echo "    https://aistudio.google.com/apikey"
echo ""
echo " This script will:"
echo "    - Install all requirements from requirements.txt"
echo "    - Start your FastAPI app with uvicorn"
echo "=============================================="
echo ""


# ================= DETECT APP FILE =================
# Default to "app:app" unless a file called main.py exists
if [ -f "main.py" ]; then
    APP_TARGET="main:app"
elif [ -f "app.py" ]; then
    APP_TARGET="app:app"
else
    echo "Could not detect FastAPI entry file. Please enter module:variable (e.g., app:app)"
    read -p "Module:Variable => " APP_TARGET
fi

# ================= START UVICORN =================
echo "Starting uvicorn server..."
uvicorn $APP_TARGET --reload --host 127.0.0.1 --port 8000

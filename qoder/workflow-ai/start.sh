#!/bin/bash
echo "Starting WorkFlow AI..."
echo ""

# Check if PowerContext is running
echo "Checking PowerContext service..."
if ! curl -s http://localhost:18080/health/ready > /dev/null 2>&1; then
    echo "WARNING: PowerContext service is not running at http://localhost:18080"
    echo "Please start PowerContext first:"
    echo "  powercontext server run --env-file .env"
    echo ""
    echo "The app will still work but semantic search will use local fallback."
    echo ""
fi

# Start the backend
echo "Starting backend server..."
cd "$(dirname "$0")"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

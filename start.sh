#!/bin/bash

# Activate Python venv
source /app/.venv/bin/activate

# Start backend
echo "Starting FastAPI backend..."
uv run -- uvicorn backend.server:app --host 0.0.0.0 --port 8000 &

# Start frontend
echo "Starting Next.js frontend..."
cd frontend
npm install
npm run build
npm run start -- -H 0.0.0.0 -p 3000

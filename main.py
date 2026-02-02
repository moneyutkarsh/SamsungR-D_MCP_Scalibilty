#!/usr/bin/env python3
"""
MCP Scalability Analysis - Main Entry Point

This script starts the FastAPI application server for the MCP scalability analysis.
"""
import sys
import os
from pathlib import Path

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv()

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the application
if __name__ == "__main__":
    import uvicorn
    from orchestrator.agent_host import app
    
    # Run the FastAPI application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

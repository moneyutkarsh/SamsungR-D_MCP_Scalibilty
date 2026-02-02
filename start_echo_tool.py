#!/usr/bin/env python3
"""
Start the Echo Tool MCP Server
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

if __name__ == "__main__":
    import uvicorn
    
    # Run the echo tool server
    uvicorn.run(
        "servers.echo_tool.server:mcp",
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )


import subprocess
import time
import asyncio
import sys
import os
import json
from dedalus_mcp.client import MCPClient

async def debug_mcp():
    print("Starting MCP Server...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "agents.mcp_server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.getcwd()
    )
    print(f"Server PID: {server_process.pid}")
    
    time.sleep(5)
    
    try:
        print("Connecting to client...")
        client = await MCPClient.connect("http://127.0.0.1:8000/mcp")
        print("Connected.")
        
        print("Listing tools...")
        tools = await client.list_tools()
        print(f"Tools found: {[t.name for t in tools.tools]}")
        
        tool_name = "delete_redundant_entries"
        print(f"Calling {tool_name}...")
        result = await client.call_tool(tool_name, {})
        
        print("Tool Result:")
        print(result.content[0].text if result.content else "No content")
        
        await client.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Check stderr
        stdout, stderr = server_process.communicate()
        print(f"Server STDERR: {stderr}")
        print(f"Server STDOUT: {stdout}")
    finally:
        server_process.terminate()

if __name__ == "__main__":
    asyncio.run(debug_mcp())

#!/usr/bin/env python3
"""
Nanobot gateway entrypoint for Docker.

Resolves environment variables into config at runtime, then launches nanobot gateway.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def install_dependencies():
    """Install MCP servers and webchat channel if not already installed."""
    # Use python -m pip to ensure we use the venv pip
    print("Installing workspace dependencies...")
    
    # Install lms-mcp from workspace
    mcp_path = Path(__file__).parent.parent / "mcp"
    if mcp_path.exists():
        print(f"Installing lms-mcp from {mcp_path}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(mcp_path)], check=True)
    
    # Install nanobot-webchat from workspace
    webchat_path = Path(__file__).parent.parent / "nanobot-websocket-channel"
    if webchat_path.exists():
        print(f"Installing nanobot-webchat from {webchat_path}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(webchat_path)], check=True)
    
    print("Dependencies installed successfully")


def resolve_config():
    """Read config.json, inject env vars, write config.resolved.json."""
    config_path = Path(__file__).parent / "config.json"
    resolved_path = Path(__file__).parent / "config.resolved.json"
    workspace_path = Path(__file__).parent / "workspace"
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Inject LLM provider config from env vars
    llm_api_key = os.environ.get("LLM_API_KEY", "")
    llm_api_base = os.environ.get("LLM_API_BASE_URL", "")
    llm_api_model = os.environ.get("LLM_API_MODEL", "coder-model")
    
    if llm_api_key:
        config["providers"]["custom"]["apiKey"] = llm_api_key
    if llm_api_base:
        config["providers"]["custom"]["apiBase"] = llm_api_base
    if llm_api_model:
        config["agents"]["defaults"]["model"] = llm_api_model
    
    # Inject gateway config from env vars
    gateway_host = os.environ.get("NANOBOT_GATEWAY_CONTAINER_ADDRESS", "0.0.0.0")
    gateway_port = os.environ.get("NANOBOT_GATEWAY_CONTAINER_PORT", "18790")
    
    config["gateway"]["host"] = gateway_host
    config["gateway"]["port"] = int(gateway_port)
    
    # Inject webchat config from env vars
    webchat_host = os.environ.get("NANOBOT_WEBCHAT_CONTAINER_ADDRESS", "0.0.0.0")
    webchat_port = os.environ.get("NANOBOT_WEBCHAT_CONTAINER_PORT", "8765")
    
    if "channels" not in config:
        config["channels"] = {}
    config["channels"]["webchat"] = {
        "enabled": True,
        "host": webchat_host,
        "port": int(webchat_port),
        "allow_from": ["*"]
    }
    
    # Inject MCP server env vars
    lms_backend_url = os.environ.get("NANOBOT_LMS_BACKEND_URL", "")
    lms_api_key = os.environ.get("NANOBOT_LMS_API_KEY", "")
    
    # Observability service URLs
    victorialogs_url = os.environ.get("VICTORIALOGS_URL", "http://victorialogs:9428")
    victoriatraces_url = os.environ.get("VICTORIATRACES_URL", "http://victoriatraces:10428")
    
    if "tools" not in config:
        config["tools"] = {}
    if "mcpServers" not in config["tools"]:
        config["tools"]["mcpServers"] = {}
    
    # LMS MCP server
    config["tools"]["mcpServers"]["lms"] = {
        "command": "python",
        "args": ["-m", "mcp_lms"],
        "env": {
            "NANOBOT_LMS_BACKEND_URL": lms_backend_url,
            "NANOBOT_LMS_API_KEY": lms_api_key
        }
    }
    
    # Observability MCP server
    config["tools"]["mcpServers"]["observability"] = {
        "command": "python",
        "args": ["-m", "mcp_observability"],
        "env": {
            "VICTORIALOGS_URL": victorialogs_url,
            "VICTORIATRACES_URL": victoriatraces_url
        }
    }
    
    # Write resolved config
    with open(resolved_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Resolved config written to {resolved_path}")
    return str(resolved_path), str(workspace_path)


def main():
    # Install workspace dependencies
    install_dependencies()
    
    resolved_config, workspace = resolve_config()
    
    # Launch nanobot gateway
    os.execvp("nanobot", ["nanobot", "gateway", "--config", resolved_config, "--workspace", workspace])


if __name__ == "__main__":
    main()

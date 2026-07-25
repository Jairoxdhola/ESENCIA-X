import json
import os
import subprocess
import sys


def main():
    print()
    print("    =========================================")
    print("           ESENCIA X - MCP Installer")
    print("    =========================================")
    print()

    print("[1/3] Installing dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "mcp", "websockets", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("       Dependencies OK")
    except Exception as e:
        print(f"       [!] Error: {e}")

    print("[2/3] Configuring opencode...")

    config_dir = os.path.join(os.environ["USERPROFILE"], ".config", "opencode")
    config_path = os.path.join(config_dir, "opencode.json")

    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")

    os.makedirs(config_dir, exist_ok=True)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}
    else:
        config = {}

    config.setdefault("$schema", "https://opencode.ai/config.json")
    config.setdefault("mcp", {})

    config["mcp"]["roblox"] = {
        "type": "local",
        "command": ["python", server_path],
        "enabled": True
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("       Configuration added!")

    print("[3/3] Done!")
    print()
    print("    =========================================")
    print("     Open bridge.lua with Potassium in Roblox")
    print("     Restart opencode and you're done")
    print("    =========================================")
    print()

    input("Press ENTER to close...")


if __name__ == "__main__":
    main()

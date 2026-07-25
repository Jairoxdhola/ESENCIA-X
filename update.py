import os
import sys
import json
import urllib.request
import ssl

BASE_URL = "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/roblox-mcp/"

FILES = [
    "server.py",
    "bridge.lua",
    "install.py",
    "requirements.txt",
    "INSTALL.bat",
    "UPDATE.bat",
    "update.py",
    "update_url.txt",
    "version.txt",
]

def download(url, destino):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "ESENCIA-X-Updater"})
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = resp.read().decode("utf-8")
        with open(destino, "w", encoding="utf-8") as f:
            f.write(data)
        print(f"       [OK] {os.path.basename(destino)}")
        return True
    except Exception as e:
        print(f"       [X] {os.path.basename(destino)}: {e}")
        return False

def main():
    print()
    print("    =========================================")
    print("       ESENCIA X - MCP Updater")
    print("    =========================================")
    print()

    here = os.path.dirname(os.path.abspath(__file__))

    url_config = os.path.join(here, "update_url.txt")
    base_url = BASE_URL
    if os.path.exists(url_config):
        with open(url_config, "r", encoding="utf-8") as f:
            base_url = f.read().strip()
            print(f"    URL: {base_url}")
            print()

    ok = 0
    fail = 0

    for archivo in FILES:
        url = base_url.rstrip("/") + "/" + archivo
        destino = os.path.join(here, archivo)
        if download(url, destino):
            ok += 1
        else:
            fail += 1

    print()
    if fail == 0:
        print(f"    [DONE] {ok} files updated!")
        print()
        print("    Restart opencode to apply changes.")
    else:
        print(f"    [WARNING] {ok} OK, {fail} failed.")
        print("    Check the URL in update_url.txt")
    print()

    input("Press ENTER to close...")

if __name__ == "__main__":
    main()

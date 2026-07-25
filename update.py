import os
import sys
import json
import subprocess
import urllib.request
import ssl

BASE_URL = "https://raw.githubusercontent.com/Jairoxdhola/ESENCIA-X/main"

FILES = [
    "server.py",
    "bridge.lua",
    "install.py",
    "requirements.txt",
    "INSTALL.bat",
    "update_url.txt",
    "version.txt",
]

SELF_UPDATE_FILES = [
    "update.py",
    "UPDATE.bat",
]

def download(url, destino):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "ESENCIA-X-Updater"})
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = resp.read().decode("utf-8")
        with open(destino, "w", encoding="utf-8") as f:
            f.write(data)
        try:
            os.remove(destino + ":Zone.Identifier")
        except OSError:
            pass
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

    self_update(here, base_url)

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

def self_update(here, base_url):
    finalize_path = os.path.join(here, "_finalize_update.bat")
    needs_finalize = False

    for archivo in SELF_UPDATE_FILES:
        url = base_url.rstrip("/") + "/" + archivo
        destino = os.path.join(here, archivo)
        if archivo == "UPDATE.bat":
            destino = destino + ".new"
        if download(url, destino):
            if archivo == "UPDATE.bat":
                needs_finalize = True

    if needs_finalize:
        bat_new = os.path.join(here, "UPDATE.bat.new")
        bat_old = os.path.join(here, "UPDATE.bat")
        with open(finalize_path, "w", encoding="utf-8") as f:
            f.write('@echo off\n')
            f.write('timeout /t 2 /nobreak >nul\n')
            f.write(f'del /f "{bat_old}" >nul 2>&1\n')
            f.write(f'ren "{bat_new}" "UPDATE.bat" >nul 2>&1\n')
            f.write(f'powershell -Command "Unblock-File \'{bat_old}\'" 2>nul\n')
            f.write(f'del /f "%~f0" >nul 2>&1\n')
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        subprocess.Popen(
            ['cmd', '/c', finalize_path],
            startupinfo=startupinfo,
            close_fds=True
        )
        print("       [OK] UPDATE.bat (will swap after exit)")

if __name__ == "__main__":
    main()

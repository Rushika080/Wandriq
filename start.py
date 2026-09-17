#!/usr/bin/env python3
"""
Wandriq — One-click setup & launcher
Run: python start.py
"""

import subprocess, sys, os, webbrowser, time

# Always work relative to THIS file's directory, no matter where you run from
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, check=True, **kw)

print("\n✦ Wandriq — AI Travel Planner\n")
print(f"  Working directory: {HERE}\n")

# Check Python version
if sys.version_info < (3, 10):
    print("⚠  Python 3.10+ required (you have", sys.version, ")")
    sys.exit(1)

# Install deps
req = os.path.join(HERE, "requirements.txt")
print("→ Installing dependencies...")
run(f'"{sys.executable}" -m pip install -r "{req}" -q')
print("  ✓ Dependencies ready\n")

# Check API key
key = os.getenv("GROQ_API_KEY", "")
if not key:
    print("────────────────────────────────────────────")
    print("  GROQ API KEY not set!")
    print("  Get your FREE key at: https://console.groq.com")
    print("  (Free account, no credit card needed)")
    print("────────────────────────────────────────────\n")
    key = input("Paste your Groq API key here (or press Enter to use demo mode): ").strip()
    if key:
        os.environ["GROQ_API_KEY"] = key
        print("  ✓ API key set for this session\n")
    else:
        print("  ℹ  Running in demo mode — itineraries will be sample data.\n")

# Launch server
print("→ Starting Wandriq at http://localhost:8000 ...")
print("  Press Ctrl+C to stop.\n")
time.sleep(1)

try:
    webbrowser.open("http://localhost:8000")
except Exception:
    pass

# Use subprocess so it works on Windows too (no os.execlp)
try:
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=HERE
    )
except KeyboardInterrupt:
    print("\n\n  Wandriq stopped. Bon voyage! ✦\n")

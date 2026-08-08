import subprocess
import sys
import os
from dotenv import load_dotenv

# Load from .env in the same directory or one level up
load_dotenv()
load_dotenv(dotenv_path="../.env")

# ── Smee URL ─────────────────────────────────────────────────────────────────
# Set your Smee URL in the .env file as SMEE_URL=https://smee.io/...
SMEE_URL = os.getenv("SMEE_URL") or "https://smee.io/your_smee_channel_id_here"

if "your_smee_channel_id_here" in SMEE_URL:
    print("=" * 70)
    print("  ERROR: SMEE_URL not configured")
    print("=" * 70)
    print("  Add your Smee channel URL to your .env file:")
    print("  SMEE_URL=https://smee.io/your_unique_id")
    print("=" * 70)
    sys.exit(1)

# ── Detect OS ─────────────────────────────────────────────────────────────────
# On Windows, npm global CLI tools are .cmd wrappers and require shell=True
IS_WINDOWS = sys.platform.startswith("win")


def run_check(cmd: list[str]) -> bool:
    """Check if a command is available. Uses shell=True on Windows."""
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            shell=IS_WINDOWS,   # <-- key fix for Windows
        )
        return True
    except Exception:
        return False


def get_smee_cmd() -> list[str]:
    """Return the correct command to run smee-client."""
    print("Checking if smee-client is available...")

    # 1. Try globally installed smee
    if run_check(["smee", "--version"]):
        print("Found: smee (global install)")
        return ["smee"]

    # 2. Try npx smee-client
    if run_check(["npx", "--version"]):
        print("Found: npx — will use 'npx smee-client'")
        return ["npx", "smee-client"]

    print("Error: Could not locate smee or npx. Please ensure Node.js is installed.")
    sys.exit(1)


smee_cmd = get_smee_cmd()

# ── Build final command ───────────────────────────────────────────────────────
cmd = smee_cmd + [
    "--url",  SMEE_URL,
    "--path", "/webhook/github",
    "--port", "8000",
]

print()
print("=" * 70)
print("  Smee Webhook Forwarder")
print("=" * 70)
print(f"  Smee URL : {SMEE_URL}")
print(f"  Target   : http://localhost:8000/webhook/github")
print("  Press Ctrl+C to stop.")
print("=" * 70)
print()

try:
    # Disable Node.js TLS verification to bypass local issuer certificate errors
    env = os.environ.copy()
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    
    subprocess.run(cmd, check=True, shell=IS_WINDOWS, env=env)
except KeyboardInterrupt:
    print("\nSmee client stopped.")
except subprocess.CalledProcessError as e:
    print(f"\nSmee client exited with error: {e}")
except Exception as e:
    print(f"\nUnexpected error: {e}")

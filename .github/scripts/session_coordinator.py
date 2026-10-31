#!/usr/bin/env python3
"""Session coordinator for complete HML lifecycle testing."""

import json
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo")

def run_cmd(cmd, check=True):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=check)
    return result.stdout.strip(), result.returncode

def wait_workflow(run_id, timeout_seconds=600):
    """Wait for workflow to complete and return success status."""
    print(f"[WAIT] Monitoring run {run_id}...")
    start = time.time()

    while time.time() - start < timeout_seconds:
        cmd = f'gh run view {run_id} --repo Software-Architecture-Group-7-FIAP/auto-shop-system --json status,conclusion'
        result, code = run_cmd(cmd, check=False)

        if code == 0:
            try:
                data = json.loads(result)
                status = data.get('status', '')
                conclusion = data.get('conclusion', '')

                if status == "completed":
                    if conclusion == "success":
                        print(f"[OK] Workflow succeeded")
                        return True
                    else:
                        print(f"[FAIL] Workflow {conclusion}")
                        return False
            except:
                pass

        time.sleep(3)

    print(f"[FAIL] Workflow timeout")
    return False

def main():
    session_id = f"hml-{datetime.now(BRT).date().isoformat()}"

    print(f"\n{'='*60}")
    print(f"Session Coordinator - Complete HML Lifecycle")
    print(f"{'='*60}")
    print(f"Session: {session_id}\n")

    # Step 1: Start session
    print("[1/2] Opening HML session (environment-start)...")
    cmd = 'gh workflow run environment-start.yml --ref main --repo Software-Architecture-Group-7-FIAP/auto-shop-system'
    stdout, code = run_cmd(cmd, check=False)

    if code != 0:
        print(f"[FAIL] Could not dispatch start workflow")
        return 1

    if "https://github.com" not in stdout:
        print(f"[FAIL] No workflow URL returned")
        return 1

    start_url = stdout.split()[-1]
    start_run_id = start_url.split('/runs/')[-1]
    print(f"[OK] Start workflow: {start_url}")

    if not wait_workflow(start_run_id):
        return 1

    # Step 2: Stop session
    print("\n[2/2] Closing HML session (environment-stop)...")
    cmd = f'gh workflow run environment-stop.yml --ref main -f session_id="{session_id}" --repo Software-Architecture-Group-7-FIAP/auto-shop-system'
    stdout, code = run_cmd(cmd, check=False)

    if code != 0:
        print(f"[FAIL] Could not dispatch stop workflow")
        return 1

    if "https://github.com" not in stdout:
        print(f"[FAIL] No workflow URL returned")
        return 1

    stop_url = stdout.split()[-1]
    stop_run_id = stop_url.split('/runs/')[-1]
    print(f"[OK] Stop workflow: {stop_url}")

    if not wait_workflow(stop_run_id):
        return 1

    print(f"\n[OK] Complete lifecycle executed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())

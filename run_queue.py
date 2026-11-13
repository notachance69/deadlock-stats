#!/usr/bin/env python3
"""Run queued deadlock_tool.py fetch commands from requests/queue.txt (one per line), then clear the queue.

Only `fetch` and `top` commands are allowed, and every output path must stay inside data/.
Lines starting with # are ignored. Results are logged to data/_last_run.txt.
"""
import os, shlex, subprocess, sys, datetime as dt

QUEUE, LOG = "requests/queue.txt", "data/_last_run.txt"
ALLOWED = {"fetch", "top"}

def safe_path(p):
    full = os.path.realpath(p)
    return full.startswith(os.path.realpath("data") + os.sep)

def check(args):
    if not args or args[0] not in ALLOWED: return "only fetch/top commands are allowed"
    for flag in ("-o", "--output", "--outdir"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args) or not safe_path(args[i + 1]): return f"{flag} must point inside data/"
    if args[0] == "fetch" and "-o" not in args and "--output" not in args: return "fetch needs -o data/..."
    if args[0] == "top" and "--outdir" not in args: args += ["--outdir", "data/top"]
    return None

lines = [l.strip() for l in open(QUEUE)] if os.path.exists(QUEUE) else []
cmds = [l for l in lines if l and not l.startswith("#")]
log = [f"Run {dt.datetime.now(dt.timezone.utc).isoformat()}"]
for line in cmds:
    args = shlex.split(line)
    err = check(args)
    if err:
        log.append(f"SKIPPED  {line}  ({err})"); continue
    for a in args:
        if a.startswith("data/") and not a.endswith(".json"): os.makedirs(a, exist_ok=True)
        elif a.startswith("data/"): os.makedirs(os.path.dirname(a), exist_ok=True)
    r = subprocess.run([sys.executable, "deadlock_tool.py", *args], capture_output=True, text=True, timeout=1500)
    log.append(f"{'OK' if r.returncode == 0 else 'FAILED'}  {line}\n{(r.stdout + r.stderr).strip()[-3000:]}")
open(LOG, "w").write("\n\n".join(log) + "\n")
open(QUEUE, "w").write("# Add one deadlock_tool.py command per line, e.g.\n# fetch history 122627581 -o data/history/122627581.json\n# top NAmerica -n 30\n")
print("\n\n".join(log))

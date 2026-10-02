#!/usr/bin/env python3
"""Claude Code status line: shows the agent's longevity and your plan usage, and saves the plan
usage (5-hour / weekly limits) to data/usage.json for Agent Board's usage panel.

Output example:  acme-app · Day 2 · 444k context · 5h 42% · week 18%
"""
import json
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USAGE_FILE = os.path.join(HERE, "data", "usage.json")


def first_day(path):
    """Date of the transcript's first timestamp (reads only the head of the file)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for _ in range(200):
                line = fh.readline()
                if not line:
                    break
                ts = json.loads(line).get("timestamp") if '"timestamp"' in line else None
                if ts:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date()
    except (OSError, ValueError):
        pass
    return None


def context_tokens(path):
    """Current context size from the last main-thread usage record (reads only the file's tail)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 400_000))
            tail = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        if '"usage"' not in line or '"assistant"' not in line:
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        u = (o.get("message") or {}).get("usage")
        if u and not o.get("isSidechain"):
            return sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return None


def pct(window):
    if not isinstance(window, dict):
        return None
    v = window.get("used_percentage", window.get("utilization"))
    return None if v is None else round(float(v))


def claude_account():
    """Email of the Claude account this Claude Code session is logged in with."""
    cfg_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    path = os.path.join(cfg_dir, ".claude.json") if cfg_dir else os.path.expanduser("~/.claude.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return (json.load(fh).get("oauthAccount") or {}).get("emailAddress") or "Claude account"
    except (OSError, ValueError):
        return "Claude account"


def save_usage(data):
    """Keep the latest plan limits per Claude account, so two accounts don't overwrite each other."""
    rl = data.get("rate_limits")
    if not isinstance(rl, dict):
        return
    os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
    try:
        with open(USAGE_FILE, encoding="utf-8") as fh:
            store = json.load(fh)
    except (OSError, ValueError):
        store = {}
    accounts = store.get("accounts") or {}
    accounts[claude_account()] = {"updated": time.time(), "rate_limits": rl}
    tmp = USAGE_FILE + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"accounts": accounts}, fh)
    os.replace(tmp, USAGE_FILE)


def main():
    data = json.load(sys.stdin)
    save_usage(data)
    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or ""
    parts = [os.path.basename(cwd.rstrip("/")) or "~"]
    path = data.get("transcript_path")
    d = first_day(path) if path else None
    if d:
        parts.append(f"Day {(datetime.now().date() - d).days + 1}")
    ctx = context_tokens(path) if path else None
    if ctx:
        parts.append(f"{ctx / 1000:.0f}k context")
    rl = data.get("rate_limits") or {}
    five, week = pct(rl.get("five_hour")), pct(rl.get("seven_day"))
    if five is not None:
        parts.append(f"5h {five}%")
    if week is not None:
        parts.append(f"week {week}%")
    print(" · ".join(parts))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Agent Board")

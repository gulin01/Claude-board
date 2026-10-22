#!/usr/bin/env python3
"""Claude Code hook: macOS notification when an agent finishes or needs you.

Registered for Stop, Notification and PreToolUse(AskUserQuestion) in ~/.claude/settings.json.
Work projects always notify; personal projects only inside personal_notify_hours (~/.agent-board/config.json).
Never blocks Claude: every failure exits 0 silently (and is logged).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402
from server import clean_prompt, extract_links  # noqa: E402


def first_sentence(text, n=90):
    t = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)          # [label](link) -> label
    t = re.sub(r"[*_`#>|]", "", t)
    line = next((l.strip(" -•\t") for l in t.splitlines() if l.strip(" -•\t")), "")
    m = re.match(r"(.+?[.!?。])(\s|$)", line)
    s = (m.group(1) if m else line).rstrip(":：")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def read_turn(path):
    """Title, first prompt, last assistant text and files edited during the latest turn."""
    title, first_prompt, last_text, files = None, None, None, set()
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return title, first_prompt, last_text, files
    with fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            t = o.get("type")
            if t == "ai-title":
                title = o.get("aiTitle") or title
            elif t == "user" and not o.get("isMeta"):
                c = (o.get("message") or {}).get("content")
                if isinstance(c, list):
                    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                        continue
                    c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                p = clean_prompt(c)
                if p:
                    first_prompt = first_prompt or p
                    files = set()           # a new turn starts
            elif t == "assistant":
                for b in (o.get("message") or {}).get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        last_text = b["text"]
                    elif b.get("type") == "tool_use" and b.get("name") in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
                        inp = b.get("input") or {}
                        files.add(inp.get("file_path") or inp.get("notebook_path"))
    return title, first_prompt, last_text, files


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    event = data.get("hook_event_name")
    cwd = data.get("cwd") or ""
    cfg = common.load_config()
    category = common.category_for(cwd, cfg)
    project = common.leaf(cwd) or "Claude"
    if common.is_scratch(cwd):
        project = "No folder"

    title, first_prompt, last_text, files = read_turn(data.get("transcript_path"))
    task = title or first_sentence(first_prompt or "", 60) or "Claude session"
    # Agent memory/scratch files don't count as project changes.
    files = {f for f in files if f and common.under(f, cwd)}

    sid = data.get("session_id") or ""
    link = common.board_link("s=" + sid if sid else "")
    head = f"{project}  ·  "

    if event == "Stop":
        if data.get("stop_hook_active"):
            return
        summary = first_sentence(last_text) or "Finished"
        n = len(files)
        body = (f"{n} file{'s' if n != 1 else ''} changed · " if n else "") + summary
        # If the agent's final message has a link (preview, PR, ticket…), clicking opens that;
        # the "View on board" button opens its card.
        links = extract_links(last_text)
        if links:
            body += f"  ↗ {links[0][:60]}"
        common.notify(category, head + "✅ Done", task, body, cfg, url=links[0] if links else link, nid=sid,
                      board_url=link if links else None)
    elif event == "Notification":
        msg = data.get("message") or "Needs your input"
        if data.get("notification_type") == "idle_prompt" or "waiting for your input" in msg.lower():
            return  # already covered by the Stop notification
        common.notify(category, head + "⏳ Needs you", task, msg.replace("Claude needs your", "Needs your"), cfg,
                      url=link, nid=sid)
    elif event == "PreToolUse" and data.get("tool_name") == "AskUserQuestion":
        qs = (data.get("tool_input") or {}).get("questions") or [{}]
        common.notify(category, head + "❓ Question", task,
                      first_sentence(qs[0].get("question"), 100) or "Has a question for you", cfg, url=link, nid=sid)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # never break the agent because of a notification
        try:
            common.log(f"ERROR notify_hook: {ex!r}")
        except Exception:
            pass
    sys.exit(0)

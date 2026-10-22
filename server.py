#!/usr/bin/env python3
"""Agent Board — a local dashboard of what every Claude agent is doing.

Reads Claude Code session transcripts (~/.claude/projects/**/*.jsonl, which covers
the CLI, the desktop app's Code tab and IDE sessions) and any events reported to
POST /api/event (for agents that don't write transcripts, e.g. Claude in Chrome).

Run:  python3 server.py          then open http://127.0.0.1:4317
Only stdlib, binds to localhost only.
"""
import base64
import glob
import hashlib
import json
import struct
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import chrome
import cleanup
import common

HOME = os.path.expanduser("~")
PROJECTS_DIR = os.environ.get("AGENT_BOARD_PROJECTS", os.path.join(HOME, ".claude", "projects"))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = common.DATA_DIR
EVENTS_FILE = os.path.join(DATA_DIR, "events.jsonl")
PORT = int(os.environ.get("AGENT_BOARD_PORT", "4317"))

WORKING_SECS = 120          # file touched this recently and turn not ended -> working
RECENT_SECS = 6 * 3600      # ended turn this recent -> "your turn"
MAX_TIMELINE = 400

_cache = {}                 # path -> (mtime, size, parsed)
_lock = threading.Lock()

NOISE_PREFIXES = ("<system-reminder", "<task-notification", "<command-", "<local-command",
                  "[SYSTEM", "<agent-message", "Caveat:", "[Request interrupted")


URL_RE = re.compile(r"https?://[^\s<>()\[\]`\"']+")


def extract_links(text, limit=5):
    """URLs an agent mentioned (e.g. its final report), in order, deduped."""
    out = []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(".,;:!?*_")
        if u not in out:
            out.append(u)
    return out[:limit]


def iso_to_epoch(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def clean_prompt(text):
    if not isinstance(text, str):
        return None
    t = text.strip()
    if not t or t.startswith(NOISE_PREFIXES):
        return None
    t = re.sub(r"</?pasted_content[^>]*>", "", t)
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S).strip()
    return t or None


def short(s, n=160):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def rel(path, cwd):
    if not path:
        return ""
    if cwd and common.under(path, cwd):
        return os.path.relpath(path, cwd).replace(os.sep, "/")
    return path.replace(HOME, "~")


def describe_tool(name, inp, cwd):
    """Turn a tool call into (kind, text) for the timeline, or None to skip."""
    inp = inp or {}
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        p = inp.get("file_path") or inp.get("notebook_path")
        return ("edit", ("Created " if name == "Write" else "Edited ") + rel(p, cwd))
    if name == "Bash":
        return ("run", inp.get("description") or short(inp.get("command"), 120))
    if name in ("Agent", "Task"):
        return ("agent", "Sub-agent: " + (inp.get("description") or short(inp.get("prompt"), 80)))
    if name == "Skill":
        return ("skill", "Skill: " + str(inp.get("skill")))
    if name == "WebSearch":
        return ("web", "Searched: " + short(inp.get("query"), 100))
    if name == "WebFetch":
        return ("web", "Fetched: " + short(inp.get("url"), 100))
    if name == "Artifact":
        return ("publish", "Artifact " + (inp.get("action") or "publish") + " " + rel(inp.get("file_path") or inp.get("url") or "", cwd))
    if name == "AskUserQuestion":
        qs = inp.get("questions") or [{}]
        return ("ask", "Asked you: " + short(qs[0].get("question"), 120))
    if name in ("Read", "Grep", "Glob", "LS", "ToolSearch", "TodoWrite", "TaskOutput"):
        return None
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = parts[1] if len(parts) > 2 else ""
        if re.fullmatch(r"[0-9a-f-]{20,}", server):
            server = ""
        tool = parts[-1]
        if tool in ("screenshot", "read_page", "get_page_text", "find", "read_me", "tabs_context", "tabs_context_mcp"):
            return None
        label = (server.replace("claude-in-chrome", "Chrome").replace("Claude_Browser", "Browser") + " · " if server else "") + tool
        detail = inp.get("url") or inp.get("jql") or inp.get("cql") or inp.get("issueIdOrKey") or inp.get("title") or ""
        return ("tool", label + (": " + short(detail, 80) if detail else ""))
    return ("tool", name)


def parse_transcript(path):
    s = {
        "id": os.path.basename(path)[:-6], "path": path, "title": None, "cwd": None,
        "branch": None, "entrypoint": None, "first_ts": None, "last_ts": None,
        "prompts": [], "timeline": [], "files": {}, "last_text": None,
        "cost": None, "lines_added": 0, "lines_removed": 0, "turn_ended": False,
        "pending_question": False, "tool_count": 0, "model": None,
        "days": {}, "context_tokens": None,
        "chrome_urls": [], "chrome_ts": None,
        "usage": [],   # [(ts, tokens)] one per API response (a response spans several records)
        "counts": {"run": 0, "page": 0},   # whole-session totals for the details panel
    }
    seen_msgs = set()
    open_asks = set()
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return s
    with fh:
        for line in fh:
            try:
                o = json.loads(line)
            except Exception:
                continue
            t = o.get("type")
            ts = iso_to_epoch(o["timestamp"]) if o.get("timestamp") else None
            if ts:
                s["first_ts"] = s["first_ts"] or ts
                s["last_ts"] = ts
            if o.get("cwd"):
                s["cwd"] = o["cwd"]
            if o.get("gitBranch"):
                s["branch"] = o["gitBranch"]
            if o.get("entrypoint"):
                s["entrypoint"] = o["entrypoint"]
            if t == "ai-title" and o.get("aiTitle"):
                s["title"] = o["aiTitle"]
            elif t == "cost-state":
                s["cost"] = o.get("totalCostUSD")
                s["lines_added"] = o.get("totalLinesAdded") or 0
                s["lines_removed"] = o.get("totalLinesRemoved") or 0
            elif t == "system" and o.get("subtype") == "turn_duration":
                s["turn_ended"] = True
            elif t == "user":
                msg = o.get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            open_asks.discard(b.get("tool_use_id"))
                    texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    has_result = any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
                    content = None if has_result else "\n".join(x for x in texts if x)
                p = None if o.get("isMeta") else clean_prompt(content)
                if p:
                    if ts:
                        day = datetime.fromtimestamp(ts).date().isoformat()
                        s["days"][day] = s["days"].get(day, 0) + 1
                    s["prompts"].append({"ts": ts, "text": short(p, 600)})
                    s["timeline"].append({"ts": ts, "kind": "prompt", "text": "You: " + short(p, 140)})
                    s["turn_ended"] = False
            elif t == "assistant":
                msg = o.get("message") or {}
                s["model"] = msg.get("model") or s["model"]
                u = msg.get("usage")
                if u and ts and msg.get("id") not in seen_msgs:
                    seen_msgs.add(msg.get("id"))
                    s["usage"].append((ts, sum(u.get(k) or 0 for k in (
                        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"))))
                if u and not o.get("isSidechain"):
                    # Tokens the model re-reads on every turn = the agent's current context size.
                    s["context_tokens"] = ((u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
                                           + (u.get("cache_creation_input_tokens") or 0))
                for b in msg.get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and b.get("text", "").strip():
                        s["last_text"] = b["text"].strip()
                    elif b.get("type") == "tool_use":
                        s["tool_count"] += 1
                        s["turn_ended"] = False
                        name, inp = b.get("name", ""), b.get("input") or {}
                        if name.startswith("mcp__claude-in-chrome__"):
                            s["chrome_ts"] = ts   # last time this agent drove Chrome
                            u = str(inp.get("url") or "")
                            if u.startswith(("http://", "https://")):
                                if u in s["chrome_urls"]:
                                    s["chrome_urls"].remove(u)
                                s["chrome_urls"].append(u)
                                s["chrome_urls"] = s["chrome_urls"][-20:]
                        if name == "AskUserQuestion":
                            open_asks.add(b.get("id"))
                        d = describe_tool(name, inp, s["cwd"])
                        if name == "Bash":
                            s["counts"]["run"] += 1
                        elif name in ("WebFetch", "WebSearch") or name.endswith("__navigate"):
                            s["counts"]["page"] += 1
                        if d:
                            s["timeline"].append({"ts": ts, "kind": d[0], "text": d[1]})
                        if d and d[0] == "edit":
                            p = inp.get("file_path") or inp.get("notebook_path")
                            s["files"][p] = s["files"].get(p, 0) + 1
    s["pending_question"] = bool(open_asks)
    s["timeline"] = s["timeline"][-MAX_TIMELINE:]
    return s


def cached_parse(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_mtime, st.st_size)
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == key:
            return hit[1], st.st_mtime
    parsed = parse_transcript(path)
    with _lock:
        _cache[path] = (key, parsed)
    return parsed, st.st_mtime


def status_for(s, mtime, now):
    age = now - mtime
    if s["pending_question"]:
        return "needs_you"
    if not s["turn_ended"] and age < WORKING_SECS:
        return "working"
    if s["turn_ended"] and age < RECENT_SECS:
        return "your_turn"
    if not s["turn_ended"] and age < RECENT_SECS:
        return "stalled"
    return "idle"


def subagents_for(session_dir, now):
    out = []
    for f in sorted(glob.glob(os.path.join(session_dir, "subagents", "*.jsonl"))):
        res = cached_parse(f)
        if not res:
            continue
        sub, mtime = res
        meta = {}
        try:
            with open(f[:-6] + ".meta.json") as m:
                meta = json.load(m)
        except Exception:
            pass
        first = sub["prompts"][0]["text"] if sub["prompts"] else ""
        out.append({
            "id": sub["id"].replace("agent-", ""),
            "description": meta.get("description") or short(first, 90),
            "type": meta.get("agentType"),
            "running": (now - mtime) < WORKING_SECS and not sub["turn_ended"] and bool(sub["timeline"] or sub["tool_count"]),
            "last_activity": mtime,
            "actions": len([x for x in sub["timeline"] if x["kind"] != "prompt"]),
            "files": [rel(p, sub["cwd"]) for p in sub["files"]],
            "summary": short(sub["last_text"], 400) if sub["last_text"] else None,
        })
    out.sort(key=lambda x: x["last_activity"], reverse=True)
    return out


def source_label(entry):
    return {"cli": "Claude Code CLI", "claude-desktop": "Desktop app", "sdk-ts": "Agent SDK",
            "sdk-py": "Agent SDK"}.get(entry or "", entry or "Claude Code")


def collect_sessions(days):
    now = time.time()
    cutoff = now - days * 86400
    cfg = common.load_config()
    sessions = []
    for path in glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl")):
        try:
            if os.stat(path).st_mtime < cutoff:
                continue
        except OSError:
            continue
        res = cached_parse(path)
        if not res:
            continue
        s, mtime = res
        if not s["prompts"] and not s["timeline"]:
            continue
        cwd = s["cwd"] or ""
        first = s["prompts"][0]["text"] if s["prompts"] else ""
        sessions.append({
            "id": s["id"],
            "kind": "claude-code",
            "title": s["title"] or short(first, 70) or "(untitled)",
            "project": "No folder" if common.is_scratch(cwd) else "Home" if os.path.normcase(os.path.normpath(cwd)) == os.path.normcase(HOME) else common.leaf(cwd) or "~",
            "cwd": cwd.replace(HOME, "~"),
            "is_scratch": common.is_scratch(cwd),
            "category": common.category_for(cwd, cfg) or "unsorted",
            "classify_key": cwd.replace(HOME, "~"),
            "branch": s["branch"],
            "source": source_label(s["entrypoint"]),
            "model": s["model"],
            "status": status_for(s, mtime, now),
            "started": s["first_ts"],
            "last_activity": mtime,
            "task": first,
            "prompts": s["prompts"][-20:],
            "timeline": s["timeline"][-150:],
            "files": sorted(({"path": rel(p, cwd), "edits": n} for p, n in s["files"].items()), key=lambda x: -x["edits"]),
            "latest": short(s["last_text"], 900) if s["last_text"] else None,
            "links": extract_links(s["last_text"]),
            "chrome_urls": s["chrome_urls"],
            "chrome_ts": s["chrome_ts"],
            "cost": s["cost"],
            "lines_added": s["lines_added"],
            "lines_removed": s["lines_removed"],
            "tool_count": s["tool_count"],
            "days": s["days"],
            "context_tokens": s["context_tokens"],
            "counts": s["counts"],
            "subagents": subagents_for(path[:-6], now),
            "_usage": s["usage"] + [e for f in glob.glob(os.path.join(path[:-6], "subagents", "*.jsonl"))
                                    for e in ((cached_parse(f) or ({"usage": []}, 0))[0]["usage"])],
        })
    sessions.extend(collect_external(cutoff, now, cfg))
    today = datetime.now().date()
    for s in sessions:
        s["life"] = longevity(s, cfg, today)
    sessions.sort(key=lambda x: x["last_activity"], reverse=True)
    return sessions


def collect_external(cutoff, now, cfg):
    """Group reported events by agent name into session-like cards."""
    if not os.path.exists(EVENTS_FILE):
        return []
    agents = {}
    with open(EVENTS_FILE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("ts", 0) < cutoff:
                continue
            key = e.get("agent") or "unnamed agent"
            a = agents.setdefault(key, {"events": [], "project": None, "source": None, "status": None, "task": None})
            a["events"].append(e)
            a["project"] = e.get("project") or a["project"]
            a["source"] = e.get("source") or a["source"]
            a["status"] = e.get("status") or a["status"]
            a["task"] = e.get("task") or a["task"]
            a["url"] = e.get("url") or a.get("url")
            if e.get("url"):
                a.setdefault("urls", [])
                if e["url"] in a["urls"]:
                    a["urls"].remove(e["url"])
                a["urls"].append(e["url"])
    out = []
    for name, a in agents.items():
        evs = a["events"]
        last = evs[-1]["ts"]
        st = (a["status"] or "").lower()
        status = {"done": "done", "blocked": "needs_you", "needs_input": "needs_you",
                  "working": "working"}.get(st, "your_turn")
        if status == "working" and now - last > 30 * 60:
            status = "stalled"
        out.append({
            "id": "ext-" + re.sub(r"\W+", "-", name.lower()),
            "kind": "external",
            "title": name,
            "project": a["project"] or "(no project)",
            "cwd": "",
            "is_scratch": False,
            "category": common.category_for(a["project"], cfg) or "unsorted",
            "classify_key": a["project"] or "",
            "branch": None,
            "source": a["source"] or "Reported",
            "model": None,
            "status": status,
            "started": evs[0]["ts"],
            "last_activity": last,
            "task": a["task"] or "",
            "prompts": [],
            "link": a.get("url"),
            "links": [a["url"]] if a.get("url") else [],
            "chrome_urls": (a.get("urls") or [])[-20:],
            "chrome_ts": last if a.get("urls") else None,
            "timeline": [{"ts": e["ts"], "kind": "report", "text": e.get("message", "")} for e in evs[-150:]],
            "files": [],
            "latest": evs[-1].get("message"),
            "cost": None, "lines_added": 0, "lines_removed": 0, "tool_count": len(evs),
            "days": day_counts(e["ts"] for e in evs), "context_tokens": None,
            "counts": {"run": 0, "page": len(a.get("urls") or [])},
            "subagents": [],
        })
    return out


def day_counts(timestamps):
    out = {}
    for ts in timestamps:
        d = datetime.fromtimestamp(ts).date().isoformat()
        out[d] = out.get(d, 0) + 1
    return out


def longevity(s, cfg, today):
    """Day N of the agent's life and whether it's time to start a fresh one."""
    first = min(s["days"]) if s["days"] else datetime.fromtimestamp(s["started"] or s["last_activity"]).date().isoformat()
    age = (today - datetime.fromisoformat(first).date()).days + 1
    fresh_days = int(cfg.get("fresh_days", 2))
    ctx_limit = int(cfg.get("context_warn_k", 250)) * 1000
    reasons = []
    if age > fresh_days:
        reasons.append("age")
    if (s.get("context_tokens") or 0) > ctx_limit:
        reasons.append("context")
    return {"first_day": first, "age_days": age, "fresh_days": fresh_days,
            "context_warn": ctx_limit, "retire": reasons}


def usage_summary(sessions, now, space=None):
    """Tokens processed (input + cache + output, incl. sub-agents) in the last 5h / today / 7 days,
    per-day bars and the heaviest agents today; plus plan limits saved by the status line."""
    today0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    h5, week = now - 5 * 3600, today0 - 6 * 86400
    days = {datetime.fromtimestamp(today0 - i * 86400).date().isoformat(): 0 for i in range(6, -1, -1)}
    tot = {"h5": 0, "today": 0, "week": 0}
    per_agent = []
    for s in sessions:
        if s["kind"] != "claude-code":
            continue
        events = list(s.pop("_usage", []))
        mine = 0
        for ts, n in events:
            if ts < week:
                continue
            tot["week"] += n
            days[datetime.fromtimestamp(ts).date().isoformat()] = days.get(datetime.fromtimestamp(ts).date().isoformat(), 0) + n
            if ts >= today0:
                tot["today"] += n
                mine += n
            if ts >= h5:
                tot["h5"] += n
        if mine:
            per_agent.append({"id": s["id"], "title": s["title"], "project": s["project"], "tokens": mine})
    per_agent.sort(key=lambda a: -a["tokens"])
    plan = []
    try:
        with open(os.path.join(DATA_DIR, "usage.json"), encoding="utf-8") as fh:
            stored = json.load(fh)
        accounts = stored.get("accounts") or ({"Claude account": stored} if "rate_limits" in stored else {})
        plan = sorted(({"account": k, **v} for k, v in accounts.items()), key=lambda a: -a["updated"])
    except (OSError, ValueError):
        pass
    cfg = common.load_config()
    if space:
        plan = [a for a in plan if common.space_of_account(a["account"], cfg) == space]
    known = [a["account"] for a in plan]
    # Claude accounts without live meters: Claude Code accounts not seen yet, and Claude used only in a
    # Chrome profile (its Claude login can differ from the profile's Google account).
    extra = [{"label": e, "sub": "Claude Code · no data yet", "email": e} for e in (cfg.get("claude_accounts") or [])
             if e not in known and (not space or common.space_of_account(e, cfg) == space)]
    profs = chrome.profiles()
    for d, info in (cfg.get("claude_in_chrome") or {}).items():
        if space and info.get("space", "personal") != space:
            continue
        name = profs.get(d, {}).get("name") or d
        extra.append({"label": info.get("claude_email") or "Claude in Chrome", "sub": f"Chrome · {name} profile", "profile": d})
    return {"tokens": tot, "days": [{"date": d, "tokens": n} for d, n in days.items()],
            "top": per_agent[:4], "plan": plan, "other_accounts": extra}


def mood(s):
    """Same mood rules as the board's characters (index.html)."""
    if s["status"] == "needs_you":
        return "need"
    if s["status"] == "working":
        return "work"
    if s.get("stale"):
        return "sleep"
    if s["status"] == "stalled":
        return "stuck"
    if s.get("life") and s["life"]["retire"]:
        return "tired"
    if s["status"] == "your_turn":
        return "done"
    return "rest"


def space_filter(sessions, space):
    return [s for s in sessions if common.in_space(s.get("category"), space)]


def summary(now, space=None):
    """Small payload for the menu-bar buddy: who needs you, who's working, plan usage (current space only)."""
    cfg = common.load_config()
    space = space or common.current_space(cfg, now)
    sessions = [s for s in space_filter(cleanup.annotate(collect_sessions(3), now), space) if not s["is_scratch"]]
    by = {}
    for s in sessions:
        by.setdefault(mood(s), []).append({"id": s["id"], "title": s["title"], "project": s["project"]})
    plan = []
    for a in usage_summary(space_filter(collect_sessions(7), space), now, space)["plan"]:
        rl = a.get("rate_limits") or {}
        pct = lambda k: None if not isinstance(rl.get(k), dict) else round(float(rl[k].get("used_percentage", rl[k].get("utilization", 0)) or 0))
        plan.append({"account": a["account"], "five": pct("five_hour"), "week": pct("seven_day")})
    return {"need": by.get("need", []), "work": by.get("work", []), "done": len(by.get("done", [])),
            "tired": len(by.get("tired", [])), "asleep": len(by.get("sleep", [])), "plan": plan,
            "space": common.space_info(cfg, now)}


def add_event(body):
    e = {
        "ts": time.time(),
        "agent": short(body.get("agent") or "unnamed agent", 80),
        "source": short(body.get("source") or "", 60) or None,
        "project": short(body.get("project") or "", 80) or None,
        "status": short(body.get("status") or "", 20) or None,
        "task": short(body.get("task") or "", 300) or None,
        "message": short(body.get("message") or "", 1000),
        "url": None,
    }
    u = str(body.get("url") or "").strip()
    if u:
        if not re.match(r"^https?://", u, re.I):
            raise ValueError("url must start with http:// or https://")
        e["url"] = u[:2000]
    if not e["message"] and not e["status"]:
        raise ValueError("message or status is required")
    os.makedirs(DATA_DIR, exist_ok=True)
    with _lock, open(EVENTS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    label = {"done": "✅ Done", "needs_input": "⏳ Needs you", "blocked": "⏳ Blocked"}.get((e["status"] or "").lower())
    if label:
        # Clicking opens the page the agent is working on (e.g. its Chrome tab), else its card on the board.
        link = e["url"] or common.board_link("s=ext-" + re.sub(r"\W+", "-", e["agent"].lower()))
        common.notify(common.category_for(e["project"]), f"{e['project'] or e['agent']}  ·  {label}",
                      e["agent"], e["message"] or e["status"], url=link, nid="ext-" + e["agent"])
    return e


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        # Blocks DNS-rebinding: only answer requests addressed to this machine by name/IP.
        host = (self.headers.get("Host") or "").lower()
        if host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return True
        self._send(403, {"error": "bad host"})
        return False

    # ---- Live connection for the Agent Board Chrome extension (WebSocket, stdlib only) ----
    def _ws_tabs(self):
        if self.headers.get("Origin") != f"chrome-extension://{chrome.EXTENSION_ID}":
            return self._send(403, {"error": "only the Agent Board extension may connect"})
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.protocol_version = "HTTP/1.1"   # browsers only accept "HTTP/1.1 101" for WebSockets
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.close_connection = True
        out_lock = threading.Lock()

        def send_frame(opcode, data):
            n = len(data)
            if n < 126:
                head = bytes([0x80 | opcode, n])
            elif n < 65536:
                head = bytes([0x80 | opcode, 126]) + struct.pack(">H", n)
            else:
                head = bytes([0x80 | opcode, 127]) + struct.pack(">Q", n)
            with out_lock:
                self.wfile.write(head + data)
                self.wfile.flush()

        cid = chrome.bridge.add(lambda msg: send_frame(1, json.dumps(msg).encode()))
        buf = b""
        try:
            while True:
                b1, b2 = self.rfile.read(2)
                opcode, n = b1 & 0x0F, b2 & 0x7F
                if n == 126:
                    n = struct.unpack(">H", self.rfile.read(2))[0]
                elif n == 127:
                    n = struct.unpack(">Q", self.rfile.read(8))[0]
                if n > 16 * 1024 * 1024:
                    break
                mask = self.rfile.read(4) if b2 & 0x80 else b"\0\0\0\0"
                data = bytes(c ^ mask[i % 4] for i, c in enumerate(self.rfile.read(n)))
                if opcode == 8:
                    break
                if opcode == 9:
                    send_frame(10, data)
                    continue
                if opcode in (0, 1):
                    buf += data
                    if not b1 & 0x80:
                        continue   # wait for the rest of a fragmented message
                    msg, buf = json.loads(buf.decode("utf-8", "replace") or "{}"), b""
                    if msg.get("type") == "hello":
                        chrome.bridge.update(cid, email=str(msg.get("email") or ""))
                    elif msg.get("type") == "tabs":
                        tabs = [t for t in msg.get("tabs") or [] if isinstance(t, dict)][:2000]
                        chrome.bridge.update(cid, email=str(msg.get("email") or ""), tabs=tabs)
        except (ValueError, OSError, struct.error):
            pass
        finally:
            chrome.bridge.remove(cid)

    def do_GET(self):
        if not self._host_ok():
            return
        u = urlparse(self.path)
        if u.path == "/ws/tabs" and self.headers.get("Upgrade", "").lower() == "websocket":
            return self._ws_tabs()
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html")
        if u.path == "/report":
            with open(os.path.join(HERE, "index.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html")
        q = parse_qs(u.query)
        cfg = common.load_config()
        space = q.get("space", [None])[0]
        space = space if space in common.CATEGORIES else common.current_space(cfg)
        if u.path == "/api/space":
            return self._send(200, common.space_info(cfg))
        if u.path == "/api/summary":
            return self._send(200, summary(time.time(), space))
        if u.path == "/api/tabs":
            try:
                # Only the Chrome profiles (Google accounts) that belong to this space.
                tabs = [dict(t) for t in chrome.list_tabs() if common.space_of_profile(t.get("profile"), cfg) == space]
            except Exception as ex:
                return self._send(200, {"tabs": [], "error": str(ex)})
            # Tag tabs an agent used: pages it opened in Chrome, reported, or linked in its final message.
            # A tab is "active" when that agent is working now or touched Chrome in the last 30 minutes.
            now = time.time()
            for s in space_filter(cleanup.annotate(collect_sessions(7), now), space):
                live = s["status"] in ("working", "needs_you") or (now - (s.get("chrome_ts") or 0) < 1800)
                for url in list(reversed(s.get("chrome_urls") or [])) + (s.get("links") or []):
                    t = chrome.find_tab(url, tabs)
                    if not t:
                        continue
                    agents = t.setdefault("agents", [])
                    if not any(a["id"] == s["id"] for a in agents):
                        agents.append({"id": s["id"], "title": s["title"], "project": s["project"],
                                       "status": s["status"], "live": live})
                    t["live"] = t.get("live") or live
            for t in tabs:
                if t.get("claude"):
                    t["agent_tab"] = True
            return self._send(200, {"tabs": tabs})
        if u.path == "/api/sessions":
            days = float(q.get("days", ["3"])[0])
            now = time.time()
            # Only this space's agents leave the server, so the other space never reaches the page.
            all7 = space_filter(collect_sessions(max(days, 7)), space)
            usage = usage_summary(all7, now, space)
            shown = [s for s in all7 if now - s["last_activity"] < days * 86400]
            trash = [t for t in cleanup.trash_list() if common.in_space(common.category_for(t["project"], cfg), space)]
            return self._send(200, {"now": now, "sessions": cleanup.annotate(shown, now), "usage": usage,
                                    "trash": trash, "space": common.space_info(cfg, now),
                                    "personal_hours": cfg["personal_notify_hours"],
                                    "personal_window_open": common.in_personal_window(cfg)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return
        route = urlparse(self.path).path
        if route not in ("/api/event", "/api/classify", "/api/session/keep", "/api/session/delete",
                         "/api/session/hide", "/api/trash/restore", "/api/trash/empty",
                         "/api/tabs/focus", "/api/tabs/open", "/api/open-in-profile", "/api/space"):
            return self._send(404, {"error": "not found"})
        # Refuse cross-site browser posts; allow curl/scripts and the board itself.
        origin = self.headers.get("Origin")
        if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
            return self._send(403, {"error": "origin not allowed"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
            if route.startswith("/api/session/"):
                s = find_session(body.get("id"))
                if route.endswith("/keep"):
                    cleanup.keep(s["id"], s["last_activity"])
                elif route.endswith("/hide"):
                    cleanup.hide(s["id"])
                else:
                    if not s["deletable"]:
                        raise ValueError("delete this session in the Claude app")
                    cleanup.delete(s, PROJECTS_DIR, EVENTS_FILE)
                return self._send(200, {"ok": True})
            if route == "/api/tabs/focus":
                chrome.focus(body.get("window"), body.get("tab"))
                return self._send(200, {"ok": True})
            if route == "/api/space":
                return self._send(200, common.set_space(str(body.get("space") or "")))
            if route == "/api/open-in-profile":
                prof = chrome.open_in_profile(str(body.get("url") or ""), str(body.get("email") or ""), body.get("profile"))
                return self._send(200, {"ok": True, "profile": prof})
            if route == "/api/tabs/open":
                return self._send(200, {"ok": True, "result": chrome.open_or_focus(str(body.get("url") or ""))})
            if route == "/api/trash/restore":
                cleanup.restore(str(body.get("id") or ""))
                return self._send(200, {"ok": True})
            if route == "/api/trash/empty":
                return self._send(200, {"ok": True, "removed": cleanup.empty_trash()})
            if route == "/api/classify":
                key = common.set_category(body.get("key") or "", body.get("category") or "")
                return self._send(200, {"ok": True, "key": key})
            self._send(200, {"ok": True, "event": add_event(body)})
        except Exception as ex:
            self._send(400, {"error": str(ex)})


def find_session(session_id):
    now = time.time()
    for s in cleanup.annotate(collect_sessions(3650), now):
        if s["id"] == session_id:
            return s
    raise ValueError("session not found")


def idle_watcher():
    """Every 30 min, remind about agents idle for 24h+ (see cleanup.py)."""
    time.sleep(60)
    while True:
        try:
            cleanup.check_and_notify(collect_sessions(30))
        except Exception as ex:
            common.log(f"ERROR idle_watcher: {ex!r}")
        time.sleep(1800)


def main():
    threading.Thread(target=idle_watcher, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Agent Board running at http://127.0.0.1:{PORT}  (reading {PROJECTS_DIR})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        print(json.dumps(collect_sessions(float(sys.argv[2]) if len(sys.argv) > 2 else 3), indent=1, ensure_ascii=False)[:6000])
    else:
        main()

#!/usr/bin/env python3
"""Agent Board connector for Claude Desktop (a local MCP server, Python standard library only).

Claude Desktop starts this program and talks to it over stdin/stdout (JSON-RPC, one message per line).
It gives Claude two tools:
  - report_progress: show this chat on Agent Board (working / done / needs you), so it appears as a tile
    and sends the usual notifications
  - list_agents:     read what your agents are doing right now

It only talks to the board on this computer (http://127.0.0.1:4317). setup.py adds it to Claude Desktop's
claude_desktop_config.json; restart Claude Desktop to load it.
"""
import json
import sys
import urllib.error
import urllib.request

BOARD = "http://127.0.0.1:4317/"
VERSION = "1.0"

INSTRUCTIONS = (
    "Agent Board is the user's local dashboard of all their Claude agents. In this chat, call report_progress "
    "when you start a task that takes several steps (status 'working'), when you finish it ('done'), and when "
    "you need the user to decide or provide something ('needs_input'). Keep the title to 2-5 words and the "
    "summary to one short sentence in the user's language. Don't report quick questions or small talk. "
    "Use list_agents when the user asks what their agents or sessions are doing."
)

TOOLS = [
    {
        "name": "report_progress",
        "title": "Report progress to Agent Board",
        "description": (
            "Show this chat's task on the user's Agent Board dashboard and notify them when it's done or needs "
            "them. Call at the start of a multi-step task (working), when finished (done), or when blocked on "
            "the user (needs_input). Use the same title for the whole task so updates stay on one tile."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short task name, 2-5 words, same for every update of this task"},
                "status": {"type": "string", "enum": ["working", "done", "needs_input", "blocked"]},
                "summary": {"type": "string", "description": "One short sentence: what was done or what you need"},
                "project": {"type": "string", "description": "Optional project or folder name, if the task belongs to one"},
                "link": {"type": "string", "description": "Optional http(s) link to the result (a preview, doc or PR)"},
            },
            "required": ["title", "status", "summary"],
        },
        "annotations": {"title": "Report progress to Agent Board", "readOnlyHint": False,
                        "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "list_agents",
        "title": "What are my agents doing?",
        "description": "List the user's Claude agents from Agent Board right now: who needs them, who is working, "
                       "how many are done or should be restarted, and plan usage.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"title": "What are my agents doing?", "readOnlyHint": True, "openWorldHint": False},
    },
]


def http(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BOARD + path, data, {"content-type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def report_progress(a):
    title = str(a.get("title") or "").strip()[:60] or "Desktop chat"
    event = {"agent": f"Desktop · {title}", "source": "Claude Desktop", "task": title,
             "status": a.get("status") or "working", "message": str(a.get("summary") or "")[:500]}
    if a.get("project"):
        event["project"] = str(a["project"])[:80]
    link = str(a.get("link") or "")
    if link.lower().startswith(("http://", "https://")):
        event["url"] = link
    http("api/event", event)
    return f"Shown on Agent Board as “{title}” ({event['status']})."


def list_agents(_a):
    s = http("api/summary")
    lines = []
    for key, label in (("need", "Needs the user"), ("work", "Working")):
        items = s.get(key) or []
        lines.append(f"{label} ({len(items)}):" if items else f"{label}: none")
        lines += [f"  - {i['title']} [{i['project']}]" for i in items[:12]]
    lines.append(f"Done: {s.get('done', 0)} · Should restart (too old/big): {s.get('tired', 0)} · Asleep 24h+: {s.get('asleep', 0)}")
    for p in s.get("plan") or []:
        lines.append(f"Plan usage {p['account']}: 5-hour {p.get('five', '–')}%, weekly {p.get('week', '–')}%")
    lines.append(f"Board: {BOARD}")
    return "\n".join(lines)


HANDLERS = {"report_progress": report_progress, "list_agents": list_agents}


def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    out["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(msg):
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if msg_id is None:
        return   # notifications (e.g. notifications/initialized) need no answer
    if method == "initialize":
        return reply(msg_id, {
            "protocolVersion": params.get("protocolVersion") or "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "agent-board", "title": "Agent Board", "version": VERSION},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return reply(msg_id, {})
    if method == "tools/list":
        return reply(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if name not in HANDLERS:
            return reply(msg_id, error={"code": -32602, "message": f"Unknown tool: {name}"})
        try:
            text, is_error = HANDLERS[name](params.get("arguments") or {}), False
        except (urllib.error.URLError, OSError):
            text, is_error = "Agent Board isn't running on this computer (http://127.0.0.1:4317). Nothing was sent.", True
        except Exception as ex:   # never crash the connector because of one bad call
            text, is_error = f"Agent Board error: {ex}", True
        return reply(msg_id, {"content": [{"type": "text", "text": text}], "isError": is_error})
    reply(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        for m in (msg if isinstance(msg, list) else [msg]):
            if isinstance(m, dict):
                handle(m)


if __name__ == "__main__":
    main()

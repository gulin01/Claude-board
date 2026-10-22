"""Idle-agent cleanup: find agents unused for 24 h, remind you once, and keep/delete/restore them.

"Delete" never destroys anything: the session's files move into data/trash/ and can be restored
from the board. Only "Empty trash" (a button you press) removes them for good.
"""
import glob
import json
import os
import re
import shutil
import threading
import time

import common
import i18n

DATA_DIR = common.DATA_DIR
STATE_FILE = os.path.join(DATA_DIR, "cleanup.json")
TRASH_DIR = os.path.join(DATA_DIR, "trash")
SESSION_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_lock = threading.RLock()


def stale_after_secs(cfg=None):
    cfg = cfg or common.load_config()
    return float(cfg.get("stale_after_hours", 24)) * 3600


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    for k in ("kept", "notified", "hidden"):
        st.setdefault(k, {})
    st.setdefault("trash", [])
    return st


def save_state(st):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def is_stale(s, st, now, limit):
    """Idle past the limit and not already kept since its last activity."""
    if now - s["last_activity"] < limit or s["status"] in ("working", "needs_you"):
        return False
    return st["kept"].get(s["id"]) != s["last_activity"]


def annotate(sessions, now):
    """Drop hidden sessions; mark stale / deletable ones for the board."""
    with _lock:
        st = load_state()
    limit = stale_after_secs()
    out = []
    for s in sessions:
        if s["id"] in st["hidden"]:
            continue
        s["stale"] = is_stale(s, st, now, limit)
        # Desktop-app sessions are also listed in the app's sidebar; delete those there.
        s["deletable"] = s["kind"] == "external" or s["source"] != "Desktop app"
        out.append(s)
    return out


def check_and_notify(sessions, now=None):
    """Send one grouped reminder per project for newly idle agents. Returns sent count."""
    now = now or time.time()
    cfg = common.load_config()
    limit = stale_after_secs(cfg)
    with _lock:
        st = load_state()
        fresh = [s for s in sessions
                 if s["id"] not in st["hidden"] and not s.get("is_scratch")
                 and is_stale(s, st, now, limit)
                 and st["notified"].get(s["id"]) != s["last_activity"]]
        sent = 0
        # One notification per project, so the project name is always the headline.
        for project in sorted({s["project"] for s in fresh}):
            group = [s for s in fresh if s["project"] == project]
            n = len(group)
            lang = i18n.language(cfg)
            title = f"{project}  ·  " + (i18n.t("idle_one", lang) if n == 1 else i18n.t("idle_many", lang, n=n))
            subtitle = ", ".join(s["title"] for s in group[:3]) + (f" +{n - 3}" if n > 3 else "")
            body = i18n.t("idle_body", lang)
            link = common.board_link("s=" + group[0]["id"] if n == 1 else "idle=all")
            common.notify(title, subtitle, body, cfg, url=link, nid="idle-" + project)
            for s in group:
                st["notified"][s["id"]] = s["last_activity"]
            sent += 1
        save_state(st)
    return sent


def keep(session_id, last_activity):
    with _lock:
        st = load_state()
        st["kept"][session_id] = last_activity
        save_state(st)


def hide(session_id):
    with _lock:
        st = load_state()
        st["hidden"][session_id] = time.time()
        save_state(st)


def _move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    return {"from": src, "to": dst}


def delete(session, projects_dir, events_file):
    """Move a session's files (or a reported agent's events) into data/trash/."""
    sid = session["id"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    items = []
    with _lock:
        if session["kind"] == "external":
            name = session["title"]
            keep_lines, gone = [], []
            with open(events_file, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        mine = (json.loads(line).get("agent") or "unnamed agent") == name
                    except ValueError:
                        mine = False
                    (gone if mine else keep_lines).append(line)
            dst = os.path.join(TRASH_DIR, f"{stamp}-{sid}.events.jsonl")
            os.makedirs(TRASH_DIR, exist_ok=True)
            with open(dst, "w", encoding="utf-8") as fh:
                fh.writelines(gone)
            with open(events_file, "w", encoding="utf-8") as fh:
                fh.writelines(keep_lines)
            items.append({"events_to": dst, "events_file": events_file})
        else:
            if not SESSION_ID.match(sid):
                raise ValueError("bad session id")
            matches = glob.glob(os.path.join(projects_dir, "*", sid + ".jsonl"))
            if not matches:
                raise ValueError("session not found")
            transcript = matches[0]
            base = os.path.join(TRASH_DIR, f"{stamp}-{sid}")
            items.append(_move(transcript, os.path.join(base, os.path.basename(transcript))))
            folder = transcript[:-6]
            if os.path.isdir(folder):
                items.append(_move(folder, os.path.join(base, sid)))
        st = load_state()
        st["trash"].append({"id": sid, "title": session["title"], "project": session["project"],
                            "deleted_at": time.time(), "items": items})
        save_state(st)


def restore(session_id):
    with _lock:
        st = load_state()
        entry = next((t for t in st["trash"] if t["id"] == session_id), None)
        if not entry:
            raise ValueError("not in trash")
        last_activity = None
        for it in entry["items"]:
            if "events_to" in it:
                with open(it["events_to"], encoding="utf-8") as src:
                    lines = src.readlines()
                with open(it["events_file"], "a", encoding="utf-8") as dst:
                    dst.writelines(lines)
                os.remove(it["events_to"])
                if lines:
                    last_activity = json.loads(lines[-1]).get("ts")
            else:
                if os.path.exists(it["from"]):
                    raise ValueError("a session with this id already exists")
                _move(it["to"], it["from"])
                if it["from"].endswith(".jsonl"):
                    last_activity = os.path.getmtime(it["from"])   # move keeps mtime
        st["trash"].remove(entry)
        st["kept"][session_id] = last_activity   # don't nag again until it's used and goes idle again
        save_state(st)


def trash_list():
    with _lock:
        return [{k: t[k] for k in ("id", "title", "project", "deleted_at")} for t in load_state()["trash"]]


def empty_trash():
    """Permanently remove everything in data/trash/. Only called from the board's button."""
    with _lock:
        st = load_state()
        n = len(st["trash"])
        if os.path.isdir(TRASH_DIR):
            shutil.rmtree(TRASH_DIR)
        st["trash"] = []
        save_state(st)
    return n

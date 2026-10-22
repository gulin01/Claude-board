"""Shared helpers: project categories (work / personal), quiet hours and macOS notifications."""
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

HOME = os.path.expanduser("~")
WINDOWS = sys.platform == "win32"


def under(path, folder):
    """True if path is inside folder (works with / and \\ separators)."""
    path, folder = os.path.normcase(os.path.normpath(path)), os.path.normcase(os.path.normpath(folder))
    return path.startswith(folder.rstrip("\\/") + os.sep)


def leaf(path):
    """Last folder name of a path, on any OS."""
    return os.path.basename(os.path.normpath(path)) if path else ""
HERE = os.path.dirname(os.path.abspath(__file__))
# Your settings and data live OUTSIDE the project folder, so the code can be shared or pushed safely:
#   macOS ~/.agent-board   ·   Windows C:\Users\<you>\.agent-board   ·   override with AGENT_BOARD_HOME
AGENT_HOME = os.environ.get("AGENT_BOARD_HOME") or os.path.join(HOME, ".agent-board")
DATA_DIR = os.path.join(AGENT_HOME, "data")
CONFIG_FILE = os.path.join(AGENT_HOME, "config.json")
LOG_FILE = os.path.join(DATA_DIR, "notify.log")


def migrate_old_layout():
    """Move config.json and data/ out of the project folder (older versions kept them inside)."""
    old_cfg, old_data = os.path.join(HERE, "config.json"), os.path.join(HERE, "data")
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(old_cfg) and not os.path.exists(CONFIG_FILE):
            os.replace(old_cfg, CONFIG_FILE)
        if os.path.isdir(old_data):
            import shutil
            for name in os.listdir(old_data):
                src, dst = os.path.join(old_data, name), os.path.join(DATA_DIR, name)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
            state = os.path.join(DATA_DIR, "cleanup.json")   # trash entries remember where their files are
            if os.path.exists(state):
                with open(state, encoding="utf-8") as fh:
                    text = fh.read()
                with open(state, "w", encoding="utf-8") as fh:
                    fh.write(text.replace(json.dumps(old_data)[1:-1], json.dumps(DATA_DIR)[1:-1]))
            if not os.listdir(old_data):
                os.rmdir(old_data)
    except OSError:
        pass


migrate_old_layout()
NOTIFIER = os.path.join(HERE, "notifier", "Agent Board.app", "Contents", "MacOS", "agent-board-notify")
BOARD_URL = "http://127.0.0.1:4317/"
CATEGORIES = ("work", "personal")

# Folders that are too general to be a "project"; sessions there are never asked about.
GENERAL_DIRS = {HOME, *(os.path.join(HOME, d) for d in ("Desktop", "Documents", "Downloads"))}

DEFAULT_CONFIG = {
    "projects": {},   # folder -> "work" | "personal"; Claude asks the first time you open a new project
    # Personal projects only notify inside this window (it may wrap past midnight).
    "personal_notify_hours": {"from": "20:00", "to": "08:00"},
    "sound": "Glass",
    # Remind about agents unused this long (cleanup.py).
    "stale_after_hours": 24,
    # Language for the board, notifications and buddies: "auto" (follow the computer), "en" or "ko".
    "language": "auto",
    # Claude Desktop chats (via the Agent Board connector) without a project: "work" or "personal".
    "desktop_chats_space": "",
    # Longevity: agents older than this many days, or with a context bigger than this, should be restarted.
    "fresh_days": 2,
    "context_warn_k": 250,
    # Spaces: which Chrome profile (Google account) and Claude account belong to Work or Personal.
    # Anything unmapped counts as personal, so it never shows up in Work by accident.
    "chrome_profiles": {},
    "account_spaces": {},
    # Browser that notification links open in (bundle id); empty = default browser.
    "browser": "com.google.Chrome",
}

_lock = threading.Lock()


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        cfg = {}
    merged = {**DEFAULT_CONFIG, **cfg}
    if not os.path.exists(CONFIG_FILE):
        save_config(merged)
    return merged


def save_config(cfg):
    with _lock:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, CONFIG_FILE)


def _norm(p):
    return os.path.normpath(os.path.expanduser(p)) if ("/" in p or p.startswith("~")) else p


def is_scratch(cwd):
    return "scratch-workspaces" in (cwd or "")


def category_for(cwd_or_name, cfg=None):
    """'work' | 'personal' | None. Matches the deepest configured folder containing cwd,
    or, for reported agents, a configured project whose folder name equals the given name."""
    if not cwd_or_name:
        return None
    cfg = cfg or load_config()
    target = _norm(cwd_or_name)
    best, best_len = None, -1
    for key, cat in cfg.get("projects", {}).items():
        k = _norm(key)
        # General folders (home, Desktop…) only match themselves, never the projects inside them.
        nested = k not in GENERAL_DIRS and under(target, k)
        same = os.path.normcase(target) == os.path.normcase(k)
        if same or nested or os.path.basename(k) == target:
            if len(k) > best_len:
                best, best_len = cat, len(k)
    return best


def reported_category(project, source, cfg=None):
    """Space for an agent that reports itself (Chrome, Claude Desktop chats): its project's space if known,
    else Claude Desktop chats follow `desktop_chats_space`; anything else stays unsorted."""
    cfg = cfg or load_config()
    cat = category_for(project, cfg) if project else None
    if not cat and source == "Claude Desktop":
        cat = cfg.get("desktop_chats_space") if cfg.get("desktop_chats_space") in CATEGORIES else None
    return cat


def needs_classification(cwd, cfg=None):
    cwd = os.path.normpath(cwd or "")
    return bool(cwd) and not is_scratch(cwd) and cwd not in GENERAL_DIRS and category_for(cwd, cfg) is None


def set_category(path_or_name, category):
    if category not in CATEGORIES and category != "unsorted":
        raise ValueError("category must be work, personal or unsorted")
    cfg = load_config()
    key = path_or_name.strip()
    if "/" in key or key.startswith("~"):
        key = os.path.normpath(os.path.expanduser(key)).replace(HOME, "~", 1)
    projects = dict(cfg.get("projects", {}))
    if category == "unsorted":
        projects.pop(key, None)
    else:
        projects[key] = category
    cfg["projects"] = projects
    save_config(cfg)
    return key


def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def in_personal_window(cfg=None, now=None):
    cfg = cfg or load_config()
    w = cfg.get("personal_notify_hours") or DEFAULT_CONFIG["personal_notify_hours"]
    start, end = _minutes(w["from"]), _minutes(w["to"])
    n = now or datetime.now()
    cur = n.hour * 60 + n.minute
    return start <= cur < end if start < end else (cur >= start or cur < end)


SPACE_FILE = os.path.join(DATA_DIR, "space.json")


def _next_boundary(cfg, now):
    """Next time the automatic space flips (the start or end of personal hours)."""
    w = cfg.get("personal_notify_hours") or DEFAULT_CONFIG["personal_notify_hours"]
    base = datetime.fromtimestamp(now).replace(second=0, microsecond=0)
    best = None
    for hhmm in (w["from"], w["to"]):
        h, m = (int(x) for x in hhmm.split(":"))
        t = base.replace(hour=h, minute=m)
        if t.timestamp() <= now:
            t = t.fromtimestamp(t.timestamp() + 86400)
        best = t.timestamp() if best is None else min(best, t.timestamp())
    return best


def current_space(cfg=None, now=None):
    """'work' or 'personal'. Follows personal hours automatically; a manual switch lasts until the next flip."""
    cfg = cfg or load_config()
    now = now or time.time()
    try:
        with open(SPACE_FILE, encoding="utf-8") as fh:
            st = json.load(fh)
        if st.get("space") in CATEGORIES and now < st.get("until", 0):
            return st["space"]
    except (OSError, ValueError):
        pass
    return "personal" if in_personal_window(cfg, datetime.fromtimestamp(now)) else "work"


def space_info(cfg=None, now=None):
    cfg = cfg or load_config()
    now = now or time.time()
    auto = "personal" if in_personal_window(cfg, datetime.fromtimestamp(now)) else "work"
    cur = current_space(cfg, now)
    return {"space": cur, "auto": auto, "manual": cur != auto, "until": _next_boundary(cfg, now)}


def set_space(space, cfg=None):
    if space not in CATEGORIES and space != "auto":
        raise ValueError("space must be work, personal or auto")
    cfg = cfg or load_config()
    os.makedirs(os.path.dirname(SPACE_FILE), exist_ok=True)
    if space == "auto":
        try:
            os.remove(SPACE_FILE)
        except OSError:
            pass
    else:
        with open(SPACE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"space": space, "until": _next_boundary(cfg, time.time())}, fh)
    return space_info(cfg)


def in_space(category, space):
    """Unsorted projects show in both spaces until you sort them (Claude asks on the first session)."""
    return category in (space, None, "unsorted")


def space_of_profile(profile_dir, cfg=None):
    cfg = cfg or load_config()
    return (cfg.get("chrome_profiles") or {}).get(profile_dir, "personal")


def space_of_account(email, cfg=None):
    cfg = cfg or load_config()
    return (cfg.get("account_spaces") or {}).get(email, "personal")


def should_notify(category, cfg=None):
    """Returns (allowed, reason). Personal: only in personal hours, or while you've switched to Personal."""
    if category == "personal" and not in_personal_window(cfg) and current_space(cfg) != "personal":
        return False, "personal project outside notify hours"
    return True, "ok"


def log(line):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")


def board_link(fragment=""):
    return BOARD_URL + ("#" + fragment if fragment else "")


# Windows toast: shown as from PowerShell; clicking opens the link. Values travel in environment
# variables, so nothing in a title or message can break out of the script.
WIN_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
function E($s) { [System.Security.SecurityElement]::Escape($s) }
$launch = if ($env:AB_URL) { " activationType=`"protocol`" launch=`"$(E $env:AB_URL)`"" } else { "" }
$audio = if ($env:AB_SOUND -eq "1") { "<audio src=`"ms-winsoundevent:Notification.Default`"/>" } else { "<audio silent=`"true`"/>" }
$xml = "<toast$launch><visual><binding template=`"ToastGeneric`"><text>$(E $env:AB_TITLE)</text><text>$(E $env:AB_SUBTITLE)</text><text>$(E $env:AB_BODY)</text></binding></visual>$audio</toast>"
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument; $doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
if ($env:AB_ID) { $toast.Tag = $env:AB_ID.Substring(0, [Math]::Min(60, $env:AB_ID.Length)) }
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""


def send_notification(title, subtitle, body, sound=True, cfg=None, url=None, nid=None, board_url=None):
    cfg = cfg or load_config()
    if WINDOWS:
        env = dict(os.environ, AB_TITLE=title or "Agent Board", AB_SUBTITLE=subtitle or "", AB_BODY=body or "",
                   AB_URL=url or board_url or "", AB_ID=nid or "", AB_SOUND="1" if sound else "0")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", WIN_TOAST],
                           env=env, capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            log(f"windows toast failed: {r.stderr.decode(errors='replace').strip()[:300]}")
        return
    if os.path.exists(NOTIFIER):
        args = [NOTIFIER, "--title", title or "Agent Board", "--subtitle", subtitle or "", "--body", body or " ",
                "--url", url or "", "--browser", cfg.get("browser") or "", "--id", nid or "",
                "--board-url", board_url or ""]
        if sound:
            args += ["--sound", cfg.get("sound") or "Glass"]
        r = subprocess.run(args, capture_output=True, timeout=30)
        if r.returncode == 0:
            return
        log(f"notifier failed ({r.returncode}): {r.stderr.decode(errors='replace').strip()} — using fallback")
    # Fallback: plain AppleScript notification (no click action, shown as Script Editor).
    script = ["on run argv",
              "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of argv)"
              + (f' sound name "{cfg.get("sound") or "Glass"}"' if sound else ""),
              "end run"]
    args = ["osascript"]
    for s in script:
        args += ["-e", s]
    args += [body or " ", title or "Claude", subtitle or ""]
    subprocess.run(args, capture_output=True, timeout=10)


def notify(category, title, subtitle, body, cfg=None, url=None, nid=None, board_url=None):
    """Send a notification if the category's rules allow it; always log the decision."""
    cfg = cfg or load_config()
    ok, reason = should_notify(category, cfg)
    log(f"{'SENT ' if ok else 'SKIP '} [{category or 'unsorted'}] {title} | {subtitle} | {body}"
        + ("" if ok else f"  ({reason})"))
    if ok:
        send_notification(title, subtitle, body, cfg=cfg, url=url, nid=nid, board_url=board_url)
    return ok

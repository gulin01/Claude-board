"""Shared helpers: settings, paths and notifications (macOS and Windows)."""
import json
import os
import subprocess
import sys
import threading
import time

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
DEFAULT_CONFIG = {
    "sound": "Glass",
    # Remind about agents unused this long (cleanup.py).
    "stale_after_hours": 24,
    # Language for the board, notifications and buddies: "auto" (follow the computer), "en" or "ko".
    "language": "auto",
    # Longevity: agents older than this many days, or with a context bigger than this, should be restarted.
    "fresh_days": 2,
    "context_warn_k": 250,
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


def is_scratch(cwd):
    return "scratch-workspaces" in (cwd or "")


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


def notify(title, subtitle, body, cfg=None, url=None, nid=None, board_url=None):
    """Send a notification and log it."""
    cfg = cfg or load_config()
    log(f"SENT  {title} | {subtitle} | {body}")
    send_notification(title, subtitle, body, cfg=cfg, url=url, nid=nid, board_url=board_url)
    return True

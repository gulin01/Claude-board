"""Find and switch to open Google Chrome tabs (via macOS scripting; no extension needed).

Two ways to see tabs:
  - the Agent Board Chrome extension (extension/, any OS): each Chrome profile reports its tabs over a live
    connection and switches tabs on request. Preferred whenever it's connected.
  - macOS only, without the extension: Chrome's AppleScript support.
Without either (e.g. Windows without the extension), links simply open in the default browser.

Incognito windows are never listed. Nothing here closes tabs or reads page contents:
only each tab's title and URL.
"""
import glob
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import webbrowser
from urllib.parse import urlsplit

WINDOWS = sys.platform == "win32"
CHROME_DIR = (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data") if WINDOWS
              else os.path.expanduser("~/Library/Application Support/Google/Chrome"))
_sess_cache = {}   # session file path -> (mtime, window ids, urls)

_cache = {"at": 0.0, "tabs": None}

EXTENSION_ID = "mfbbhdnaghpjhkjkgckcnlcebkmcnakl"   # fixed by the "key" in extension/manifest.json
NEEDS_EXTENSION = "Load the Agent Board Chrome extension to find your tabs (see README → Chrome tab finder)."


class Bridge:
    """Live connections from the Chrome extension, one per Chrome profile."""

    def __init__(self):
        self.lock = threading.Lock()
        self.conns = {}   # id -> {"email", "tabs", "updated", "send"}
        self.next_id = 0

    def add(self, send):
        with self.lock:
            self.next_id += 1
            self.conns[self.next_id] = {"email": "", "tabs": [], "updated": 0.0, "send": send}
            return self.next_id

    def remove(self, cid):
        with self.lock:
            self.conns.pop(cid, None)
        _cache["tabs"] = None

    def update(self, cid, email=None, tabs=None):
        with self.lock:
            c = self.conns.get(cid)
            if not c:
                return
            if email is not None:
                c["email"] = email
            if tabs is not None:
                c["tabs"], c["updated"] = tabs, time.time()
        _cache["tabs"] = None

    def connected(self):
        with self.lock:
            return bool(self.conns)

    def snapshot(self):
        with self.lock:
            return [(cid, c["email"], list(c["tabs"])) for cid, c in self.conns.items()]

    def send(self, cid, msg):
        with self.lock:
            c = self.conns.get(cid)
        if c:
            c["send"](msg)
            return True
        return False

    def owner(self, window_id):
        for cid, _email, tabs in self.snapshot():
            if any(t["window"] == window_id for t in tabs):
                return cid
        return None


bridge = Bridge()


def _bridge_tabs():
    """Tabs reported by the extension, tagged with their Chrome profile like the AppleScript path."""
    by_email = {p["email"].lower(): (d, p) for d, p in profiles().items() if p["email"]}
    out, windows = [], {}
    for _cid, email, tabs in bridge.snapshot():
        prof = by_email.get((email or "").lower())
        for t in tabs:
            wn = windows.setdefault(t["window"], len(windows) + 1)
            item = {"window": t["window"], "wn": wn, "tab": t["tab"], "index": t.get("index", 0),
                    "active": bool(t.get("active")), "title": t.get("title", ""), "url": t.get("url", "")}
            if prof:
                item.update(profile=prof[0], profile_name=prof[1]["name"], profile_email=prof[1]["email"])
            elif email:
                item.update(profile=email, profile_name=email, profile_email=email)
            out.append(item)
    return out


def chrome_exe():
    """Path to chrome.exe on Windows, or None."""
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
        p = os.path.join(base or "", "Google", "Chrome", "Application", "chrome.exe")
        if base and os.path.exists(p):
            return p
    return None


def _jxa(script, *args):
    if WINDOWS:
        raise RuntimeError(NEEDS_EXTENSION)
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", script, *args],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "-1743" in err or "Not authorized" in err:
            raise PermissionError("Allow Agent Board to control Chrome: System Settings → Privacy & Security → "
                                  "Automation → python3 → Google Chrome")
        raise RuntimeError(err or "osascript failed")
    return r.stdout.strip()


LIST = """
function run() {
  const c = Application("Google Chrome");
  if (!c.running()) return "[]";           // never launch Chrome just to list tabs
  const ids = c.windows.id(), modes = c.windows.mode(), active = c.windows.activeTabIndex();
  const tid = c.windows.tabs.id(), title = c.windows.tabs.title(), url = c.windows.tabs.url();
  const out = [];
  for (let w = 0; w < ids.length; w++) {
    if (modes[w] === "incognito") continue;
    for (let t = 0; t < tid[w].length; t++)
      out.push({window: ids[w], wn: w + 1, tab: tid[w][t], index: t + 1, active: active[w] === t + 1,
                title: title[w][t], url: url[w][t]});
  }
  return JSON.stringify(out);
}
"""

FOCUS = """
function run(argv) {
  const c = Application("Google Chrome"), wid = Number(argv[0]), tabId = Number(argv[1]);
  const w = c.windows.byId(wid), ids = w.tabs.id(), i = ids.indexOf(tabId);
  if (i < 0) throw new Error("tab not found");
  w.activeTabIndex = i + 1;
  w.index = 1;
  c.activate();
  return "ok";
}
"""

OPEN = """
function run(argv) {
  const c = Application("Google Chrome");
  c.activate();
  if (c.windows.length === 0) c.Window().make();
  const w = c.windows[0];
  w.tabs.push(c.Tab({url: argv[0]}));
  w.activeTabIndex = w.tabs.length;
  return "opened";
}
"""


def _session_info(path):
    """Window ids (and page URLs) recorded in a profile's Chrome session file (SNSS format)."""
    mt = os.path.getmtime(path)
    hit = _sess_cache.get(path)
    if hit and hit[0] == mt:
        return hit[1], hit[2]
    data = open(path, "rb").read()
    wins = set()
    if data[:4] == b"SNSS":
        i = 8
        while i + 2 <= len(data):
            size = struct.unpack_from("<H", data, i)[0]
            i += 2
            if size == 0 or i + size > len(data):
                break
            if data[i] == 0 and size == 9:      # kCommandSetTabWindow: {window_id, tab_id}
                wins.add(struct.unpack_from("<i", data, i + 1)[0])
            i += size
    urls = {m.decode("utf-8", "replace") for m in re.findall(rb"(?:https?|file)://[\x21-\x7e]{3,2000}", data)}
    _sess_cache[path] = (mt, wins, urls)
    return wins, urls


def profiles():
    """{profile dir: {"name", "email", "windows", "urls"}} for every Chrome profile (Google account)."""
    try:
        with open(os.path.join(CHROME_DIR, "Local State"), encoding="utf-8") as fh:
            info = json.load(fh)["profile"]["info_cache"]
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for d, v in info.items():
        files = sorted(glob.glob(os.path.join(CHROME_DIR, d, "Sessions", "Session_*")), key=os.path.getmtime)
        wins, urls = _session_info(files[-1]) if files else (set(), set())
        out[d] = {"name": v.get("name") or d, "email": v.get("user_name") or "", "windows": wins, "urls": urls}
    return out


def _tag_profiles(tabs):
    profs = profiles()
    if not profs:
        return
    by_window = {}
    for t in tabs:
        by_window.setdefault(t["window"], []).append(t)
    for wid, ts in by_window.items():
        match = [d for d, p in profs.items() if int(wid) in p["windows"]]
        if not match:   # window newer than the last session save: fall back to which profile knows its pages
            scores = {d: sum(t["url"] in p["urls"] for t in ts) for d, p in profs.items()}
            best = max(scores, key=scores.get)
            match = [best] if scores[best] else []
        if match:
            p = profs[match[0]]
            for t in ts:
                t.update(profile=match[0], profile_name=p["name"], profile_email=p["email"])


CLAUDE_KINDS = {"design": "Claude Design", "chat": "Claude chat", "project": "Claude project", "code": "Claude Code (web)"}


def claude_kind(url):
    """'Claude Design' / 'Claude chat' / … for claude.ai tabs, else None."""
    p = urlsplit(url)
    if (p.hostname or "") not in ("claude.ai", "www.claude.ai"):
        return None
    first = p.path.strip("/").split("/")[0]
    return CLAUDE_KINDS.get(first, "claude.ai")


def open_in_profile(url, email=None, profile=None):
    """Open url in a Chrome profile, given by folder name or by its Google account (e.g. a usage page)."""
    if not url.startswith("https://claude.ai/"):
        raise ValueError("only claude.ai pages")
    profs = profiles()
    prof = profile if profile in profs else next((d for d, p in profs.items() if p["email"].lower() == (email or "").lower()), None)
    if WINDOWS:
        exe = chrome_exe()
        if not exe:
            webbrowser.open(url)
            return None
        subprocess.Popen([exe] + ([f"--profile-directory={prof}"] if prof else []) + [url])
        return prof
    args = ["open", "-na", "Google Chrome", "--args"] + ([f"--profile-directory={prof}"] if prof else []) + [url]
    subprocess.run(args, check=True, timeout=15)
    return prof


def list_tabs(max_age=2.0):
    if _cache["tabs"] is not None and time.time() - _cache["at"] < max_age:
        return _cache["tabs"]
    if bridge.connected():
        tabs = _bridge_tabs()
    else:
        tabs = json.loads(_jxa(LIST) or "[]")
        try:
            _tag_profiles(tabs)
        except Exception:
            pass   # profile tags are a nice-to-have; never break the tab list
    for t in tabs:
        k = claude_kind(t["url"])
        if k:
            t["claude"] = k
    _cache.update(at=time.time(), tabs=tabs)
    return tabs


def focus(window_id, tab_id):
    cid = bridge.owner(int(window_id)) if bridge.connected() else None
    if cid:
        bridge.send(cid, {"type": "focus", "window": int(window_id), "tab": int(tab_id)})
        return
    _jxa(FOCUS, str(int(window_id)), str(int(tab_id)))
    _cache["tabs"] = None


def _norm(u):
    p = urlsplit(u)
    host = (p.hostname or "").replace("localhost", "127.0.0.1")
    return (host, p.port, p.path.rstrip("/") or "/", p.query)


def find_tab(url, tabs=None):
    """Best open tab for url: same page first, then the same site (host+port)."""
    tabs = tabs if tabs is not None else list_tabs(0)
    want = _norm(url)
    exact = [t for t in tabs if _norm(t["url"])[:3] == want[:3]]
    if exact:
        return exact[0]
    if want[2] == "/":   # a bare site link (e.g. http://127.0.0.1:4000) matches any page on that site
        same = [t for t in tabs if _norm(t["url"])[:2] == want[:2]]
        if same:
            return same[0]
    return None


def open_or_focus(url):
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("only http(s) links")
    if bridge.connected():
        t = find_tab(url)
        if t:
            focus(t["window"], t["tab"])
            return "focused"
        # Open it in a Chrome profile that belongs to the current space (work links in the work profile).
        import common
        space = common.current_space()
        conns = bridge.snapshot()
        profs = {p["email"].lower(): d for d, p in profiles().items() if p["email"]}
        pick = next((cid for cid, email, _ in conns
                     if common.space_of_profile(profs.get((email or "").lower()), None) == space), conns[0][0])
        bridge.send(pick, {"type": "open", "url": url})
        return "opened"
    if WINDOWS:
        webbrowser.open(url)
        return "opened"
    t = find_tab(url)
    if t:
        focus(t["window"], t["tab"])
        return "focused"
    _jxa(OPEN, url)
    _cache["tabs"] = None
    return "opened"

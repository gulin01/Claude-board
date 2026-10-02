#!/usr/bin/env python3
"""Agent Board setup: asks a few questions, then installs everything.

    python3 setup.py              # interactive setup (safe to run again to change answers)
    python3 setup.py --yes        # accept every default, no questions
    python3 setup.py --dry-run    # show what would happen, change nothing
    python3 setup.py --uninstall  # remove hooks, login items and the Desktop shortcut (keeps your data)

What it asks:
  1. Your personal hours (personal notifications only arrive then; the board switches to Personal then)
  2. Which of your Claude Code project folders are Work and which are Personal
  3. Which Chrome profiles (Google accounts) are Work and which are Personal
  4. Which Claude accounts are Work and which are Personal
What it installs:
  - Claude Code hooks + status line in ~/.claude/settings.json (a backup is saved next to it)
  - the Agent Board app (board window + notifications) and the menu-bar buddy, if Xcode tools exist
  - login items so the board and menu-bar buddy start when you log in
  - an "Agent Board" shortcut on your Desktop
Everything runs only on this Mac. Nothing is sent anywhere.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
CLAUDE_JSON = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or HOME, ".claude.json")
CONFIG = os.path.join(HERE, "config.json")
EXAMPLE = os.path.join(HERE, "config.example.json")
AGENTS = os.path.join(HOME, "Library", "LaunchAgents")
CHROME_STATE = os.path.join(HOME, "Library", "Application Support", "Google", "Chrome", "Local State")
NOTIFIER_APP = os.path.join(HERE, "notifier", "Agent Board.app")
MENU_APP = os.path.join(HERE, "menubar", "Agent Board Menu.app")
DESKTOP_LINK = os.path.join(HOME, "Desktop", "Agent Board.app")
GENERAL = {HOME, *(os.path.join(HOME, d) for d in ("Desktop", "Documents", "Downloads"))}

YES = "--yes" in sys.argv
DRY = "--dry-run" in sys.argv

B, D, G, Y, R, X = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def say(msg=""): print(msg)
def step(n, title): say(f"\n{B}{n}. {title}{X}")
def ok(msg): say(f"   {G}✓{X} {msg}")
def warn(msg): say(f"   {Y}!{X} {msg}")
def tilde(p): return p.replace(HOME, "~", 1)


def ask(question, default=""):
    if YES:
        return default
    hint = f" {D}[{default}]{X}" if default else ""
    try:
        a = input(f"   {question}{hint} ").strip()
    except EOFError:
        a = ""
    return a or default


def ask_space(label, default="p"):
    """w / p / s(kip). Returns 'work', 'personal' or None."""
    while True:
        a = ask(f"{label}  {D}(w = work, p = personal, s = skip){X}", default).lower()[:1]
        if a in ("w", "p", "s"):
            return {"w": "work", "p": "personal", "s": None}[a]
        say("   Please type w, p or s.")


def write(path, text):
    if DRY:
        say(f"   {D}would write {tilde(path)}{X}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def run(args, check=True):
    if DRY:
        say(f"   {D}would run: {' '.join(args)}{X}")
        return subprocess.CompletedProcess(args, 0, "", "")
    return subprocess.run(args, capture_output=True, text=True, check=check)


# ---------------------------------------------------------------- discovery
def project_folders():
    """Folders you've used Claude Code in (most recent first), read from Claude Code's own logs."""
    seen = {}
    for f in glob.glob(os.path.join(CLAUDE_DIR, "projects", "*", "*.jsonl")):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for _ in range(60):
                    line = fh.readline()
                    if not line:
                        break
                    if '"cwd"' in line:
                        cwd = json.loads(line).get("cwd")
                        if cwd:
                            seen[cwd] = max(seen.get(cwd, 0), os.path.getmtime(f))
                            break
        except (OSError, ValueError):
            continue
    out = [c for c in sorted(seen, key=seen.get, reverse=True)
           if c not in GENERAL and "scratch-workspaces" not in c and os.path.isdir(c)]
    # Keep top-level project folders only (subfolders follow their parent).
    tops = []
    for c in out:
        if not any(c.startswith(t.rstrip("/") + "/") for t in tops):
            tops = [t for t in tops if not t.startswith(c.rstrip("/") + "/")] + [c]
    return tops[:25]


def chrome_profiles():
    try:
        with open(CHROME_STATE, encoding="utf-8") as fh:
            info = json.load(fh)["profile"]["info_cache"]
        return {d: (v.get("name") or d, v.get("user_name") or "") for d, v in info.items()}
    except (OSError, ValueError, KeyError):
        return {}


def claude_code_account():
    try:
        with open(CLAUDE_JSON, encoding="utf-8") as fh:
            return (json.load(fh).get("oauthAccount") or {}).get("emailAddress")
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- questions
def configure():
    cfg = {}
    for path in (EXAMPLE, CONFIG):
        try:
            with open(path, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (OSError, ValueError):
            pass
    fresh = not os.path.exists(CONFIG)
    if fresh:   # start from a clean slate, not the example's placeholder folders and emails
        cfg.update(projects={}, chrome_profiles={}, account_spaces={}, claude_accounts=[], claude_in_chrome={})

    step(1, "Personal hours")
    say(f"   {D}During these hours the board shows your Personal space and personal notifications can arrive.")
    say(f"   The rest of the day is Work: personal projects stay hidden from the screen.{X}")
    h = cfg.get("personal_notify_hours") or {"from": "20:00", "to": "08:00"}
    h = {"from": ask("Personal time starts at", h["from"]), "to": ask("Personal time ends at", h["to"])}
    cfg["personal_notify_hours"] = h
    ok(f"Personal {h['from']}–{h['to']}, Work the rest of the day")

    step(2, "Your project folders")
    say(f"   {D}Folders you've used Claude Code in. Subfolders follow their parent.")
    say(f"   New projects later: Claude asks you \"work or personal?\" the first time you open them.{X}")
    projects = dict(cfg.get("projects") or {})
    folders = project_folders()
    if not folders:
        warn("No Claude Code projects found yet. That's fine: Claude will ask when you start one.")
    for c in folders:
        key = tilde(c)
        cur = projects.get(key)
        sp = ask_space(f"{B}{key}{X}", {"work": "w", "personal": "p"}.get(cur, "s"))
        if sp:
            projects[key] = sp
        else:
            projects.pop(key, None)
    cfg["projects"] = projects
    ok(f"{sum(v == 'work' for v in projects.values())} work, {sum(v == 'personal' for v in projects.values())} personal")

    step(3, "Chrome profiles (Google accounts)")
    say(f"   {D}Tabs from a Work profile only show in Work; anything not marked Work stays Personal.{X}")
    profs = chrome_profiles()
    cp = dict(cfg.get("chrome_profiles") or {})
    cic = dict(cfg.get("claude_in_chrome") or {})
    if not profs:
        warn("Google Chrome not found. Skipping (the Chrome tab finder needs Chrome).")
    for d, (name, email) in profs.items():
        sp = ask_space(f"{B}{name}{X} {D}{email}{X}", "w" if cp.get(d) == "work" else "p") or "personal"
        cp[d] = sp
        uses = ask(f"   Do you use Claude (extension or claude.ai) in {name}? (y/n)", "y" if d in cic else "n").lower().startswith("y")
        if uses:
            cic[d] = {"space": sp, "claude_email": cic.get(d, {}).get("claude_email", "")}
        else:
            cic.pop(d, None)
    cfg["chrome_profiles"], cfg["claude_in_chrome"] = cp, cic
    if profs:
        ok(f"{sum(v == 'work' for v in cp.values())} work profile(s), {sum(v == 'personal' for v in cp.values())} personal")

    step(4, "Claude accounts")
    acct = claude_code_account()
    spaces = dict(cfg.get("account_spaces") or {})
    accounts = [a for a in (cfg.get("claude_accounts") or []) if "@" in a]
    if acct:
        sp = ask_space(f"Claude Code is signed in as {B}{acct}{X}", "w" if spaces.get(acct, "work") == "work" else "p") or "work"
        spaces[acct] = sp
        if acct not in accounts:
            accounts.insert(0, acct)
        ok(f"{acct} → {sp}")
    else:
        warn("Claude Code isn't signed in yet. Run setup again after your first Claude Code session.")
    cfg["account_spaces"], cfg["claude_accounts"] = spaces, accounts

    write(CONFIG, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    ok(f"Saved your answers in {tilde(CONFIG)} (edit it anytime, or run setup again)")
    return cfg


# ---------------------------------------------------------------- install
def hook_cmd(script):
    p = os.path.join(HERE, "hooks", script)
    return f'f="{p}"; [ -f "$f" ] && python3 "$f"; exit 0'


def is_ours(entry):
    return HERE in json.dumps(entry) or "agent-board/hooks/" in json.dumps(entry)


def install_hooks():
    step(5, "Claude Code hooks and status line")
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            settings = json.load(fh)
    except FileNotFoundError:
        settings = {}
    except ValueError:
        warn(f"{tilde(SETTINGS)} isn't valid JSON. Fix it, then run setup again.")
        return
    if os.path.exists(SETTINGS) and not DRY:
        shutil.copy2(SETTINGS, f"{SETTINGS}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    hooks = settings.setdefault("hooks", {})
    notify = {"type": "command", "command": hook_cmd("notify_hook.py"), "async": True, "timeout": 20}
    wanted = {
        "Stop": {"hooks": [notify]},
        "Notification": {"hooks": [notify]},
        "PreToolUse": {"matcher": "AskUserQuestion", "hooks": [notify]},
        "SessionStart": {"matcher": "startup", "hooks": [{"type": "command", "command": hook_cmd("session_start_hook.py"), "timeout": 10}]},
    }
    for event, entry in wanted.items():
        # Replace an earlier Agent Board entry, keep everything else you already had.
        hooks[event] = [e for e in hooks.get(event, []) if not is_ours(e)] + [entry]
    sl = os.path.join(HERE, "hooks", "statusline.py")
    line = {"type": "command", "command": f'f="{sl}"; [ -f "$f" ] && python3 "$f" || echo ""', "padding": 0}
    cur = settings.get("statusLine")
    if cur and not is_ours(cur):
        if ask(f"You already have a status line ({cur.get('command', '')[:40]}…). Replace it? (y/n)", "n").lower().startswith("y"):
            settings["statusLine"] = line
        else:
            warn("Kept your status line. Plan usage (5-hour / weekly %) won't show on the board.")
    else:
        settings["statusLine"] = line
    write(SETTINGS, json.dumps(settings, indent=2) + "\n")
    ok(f"Hooks added to {tilde(SETTINGS)} (backup saved next to it)")
    ok("Open Claude Code sessions pick this up after a restart")


def build_apps():
    step(6, "Apps")
    if not shutil.which("swiftc"):
        warn("Xcode command line tools not found, so the app and menu-bar buddy were skipped.")
        warn("Install them with:  xcode-select --install   then run setup again.")
        warn("The board still works in your browser at http://127.0.0.1:4317")
        return False
    for script, what in (("notifier/build.sh", "Agent Board app (board window + notifications)"),
                         ("menubar/build.sh", "Menu-bar buddy")):
        r = run([os.path.join(HERE, script)], check=False)
        ok(f"Built {what}") if r.returncode == 0 else warn(f"Couldn't build {what}: {(r.stderr or '')[-300:]}")
    return True


def plist(label, args, keep_alive):
    arr = "".join(f"<string>{a}</string>" for a in args)
    ka = "<true/>" if keep_alive else "<dict><key>SuccessfulExit</key><false/></dict>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>{arr}</array>
  <key>WorkingDirectory</key><string>{HERE}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>{ka}
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>/tmp/{label}.log</string>
  <key>StandardErrorPath</key><string>/tmp/{label}.log</string>
</dict></plist>
"""


def login_items(apps_built):
    step(7, "Start at login")
    uid = str(os.getuid())
    items = [("com.agent-board.server", [sys.executable, os.path.join(HERE, "server.py")], True, "Board server")]
    menu_bin = os.path.join(MENU_APP, "Contents", "MacOS", "agent-board-menu")
    if apps_built and (os.path.exists(menu_bin) or DRY):
        items.append(("com.agent-board.menubar", [menu_bin], False, "Menu-bar buddy"))
    for label, args, keep, what in items:
        path = os.path.join(AGENTS, label + ".plist")
        run(["launchctl", "bootout", f"gui/{uid}/{label}"], check=False)
        write(path, plist(label, args, keep))
        r = run(["launchctl", "bootstrap", f"gui/{uid}", path], check=False)
        ok(f"{what} starts at login") if r.returncode == 0 else warn(f"{what}: {r.stderr.strip()}")


def shortcut():
    if not os.path.exists(NOTIFIER_APP) and not DRY:
        return
    if not DRY:
        if os.path.islink(DESKTOP_LINK):
            os.remove(DESKTOP_LINK)
        if not os.path.exists(DESKTOP_LINK):
            os.symlink(NOTIFIER_APP, DESKTOP_LINK)
    ok("Added “Agent Board” to your Desktop")


def uninstall():
    say(f"{B}Removing Agent Board from Claude Code and login items{X} {D}(your data and config stay){X}")
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            settings = json.load(fh)
        for event in list((settings.get("hooks") or {})):
            settings["hooks"][event] = [e for e in settings["hooks"][event] if not is_ours(e)]
            if not settings["hooks"][event]:
                del settings["hooks"][event]
        if settings.get("statusLine") and is_ours(settings["statusLine"]):
            del settings["statusLine"]
        write(SETTINGS, json.dumps(settings, indent=2) + "\n")
        ok("Hooks and status line removed")
    except (OSError, ValueError):
        pass
    for label in ("com.agent-board.server", "com.agent-board.menubar"):
        run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], check=False)
        p = os.path.join(AGENTS, label + ".plist")
        if os.path.exists(p) and not DRY:
            os.remove(p)
    ok("Login items removed")
    if os.path.islink(DESKTOP_LINK) and not DRY:
        os.remove(DESKTOP_LINK)
    ok("Desktop shortcut removed")


def main():
    if sys.platform != "darwin":
        sys.exit("Agent Board runs on macOS only.")
    if sys.version_info < (3, 9):
        sys.exit("Please use Python 3.9 or newer.")
    if "--uninstall" in sys.argv:
        return uninstall()
    say(f"\n{B}Agent Board setup{X}  {D}{'(dry run: nothing will change)' if DRY else ''}{X}")
    say(f"{D}A few questions, then everything installs. Press Enter to accept the [default].{X}")
    if not os.path.isdir(CLAUDE_DIR):
        warn("Claude Code doesn't seem to be installed yet (no ~/.claude). Install it first, then run setup again.")
    configure()
    install_hooks()
    built = build_apps()
    login_items(built)
    shortcut()
    say(f"\n{G}{B}Done.{X} Open {B}Agent Board{X} on your Desktop, or http://127.0.0.1:4317")
    say(f"{D}macOS may ask to allow notifications from Agent Board, and to let python3 control Google Chrome")
    say(f"(for the tab finder). Both are optional. Restart open Claude Code sessions to load the hooks.{X}\n")
    if not DRY and os.path.exists(NOTIFIER_APP):
        time.sleep(2)
        subprocess.run(["open", NOTIFIER_APP], check=False)


if __name__ == "__main__":
    main()

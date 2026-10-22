#!/usr/bin/env python3
"""Agent Board setup: asks a few questions, then installs everything.

    python3 setup.py              # interactive setup (safe to run again to change answers)
                                  # on Windows:  py setup.py
    python3 setup.py --yes        # accept every default, no questions
    python3 setup.py --dry-run    # show what would happen, change nothing
    python3 setup.py --uninstall  # remove hooks, login items and the Desktop shortcut (keeps your data)

For Claude (or scripts): no typed questions needed.
    python3 setup.py --detect               # prints JSON: OS, what's installed, Chrome profiles, account
    python3 setup.py --answers answers.json # installs with these answers (format: see CLAUDE.md)

What it asks: your language, and whether you use Claude in each Chrome profile.
What it installs (and, for the Chrome tab finder, walks you through 3 clicks in Chrome):
  - Claude Code hooks + status line in ~/.claude/settings.json (a backup is saved next to it)
  - Mac: the Agent Board app (board window + notifications) and the menu-bar buddy, if Xcode tools exist
  - start at login (Mac: login items · Windows: Startup folder)
  - an "Agent Board" shortcut on your Desktop (Windows: opens the board in its own Chrome/Edge window)
Everything runs only on this computer. Nothing is sent anywhere.
"""
import glob
import json
import re
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
WINDOWS = sys.platform == "win32"
BOARD = "http://127.0.0.1:4317/"
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
CLAUDE_JSON = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or HOME, ".claude.json")
AGENT_HOME = os.environ.get("AGENT_BOARD_HOME") or os.path.join(HOME, ".agent-board")   # your data, outside the project
CONFIG = os.path.join(AGENT_HOME, "config.json")
EXAMPLE = os.path.join(HERE, "config.example.json")
AGENTS = os.path.join(HOME, "Library", "LaunchAgents")
CHROME_STATE = (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "Local State") if WINDOWS
                else os.path.join(HOME, "Library", "Application Support", "Google", "Chrome", "Local State"))
WIN_STARTUP = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Agent Board.vbs")
HOOK_SCRIPTS = ("notify_hook.py", "session_start_hook.py", "statusline.py")
EXTENSION_DIR = os.path.join(HERE, "extension")
CONNECTOR = os.path.join(HERE, "connector", "agent_board_mcp.py")
DESKTOP_DIR = (os.path.join(os.environ.get("APPDATA", ""), "Claude") if WINDOWS
               else os.path.join(HOME, "Library", "Application Support", "Claude"))
DESKTOP_CONFIG = os.path.join(DESKTOP_DIR, "claude_desktop_config.json")
TRAY = os.path.join(HERE, "tray", "tray.ps1")
NOTIFIER_APP = os.path.join(HERE, "notifier", "Agent Board.app")
MENU_APP = os.path.join(HERE, "menubar", "Agent Board Menu.app")
DESKTOP_LINK = os.path.join(HOME, "Desktop", "Agent Board.app")

YES = "--yes" in sys.argv
DRY = "--dry-run" in sys.argv

if WINDOWS:
    os.system("")   # turns on colors in the Windows console
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
B, D, G, Y, R, X = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"



# ---------------------------------------------------------------- Korean
# Setup's messages pass through tr(); when the user picks 한국어, these patterns translate them.
KO = [(re.compile(p), r) for p, r in [
    (r"Agent Board setup", "Agent Board 설정"),
    (r"\(dry run: nothing will change\)", "(미리보기: 아무것도 바뀌지 않아요)"),
    (r"A few questions, then everything installs\. Press Enter to accept the \[default\]\.", "몇 가지 질문 후 모두 설치돼요. Enter를 누르면 [기본값]을 써요."),
    (r"Google Chrome not found\. Skipping \(the Chrome tab finder needs Chrome\)\.", "Google Chrome이 없어서 건너뛰어요 (탭 찾기는 Chrome이 필요해요)."),
    (r"Do you use Claude \(extension or claude\.ai\) in (.+)\? \(y/n\)", r"\1에서 Claude(확장 프로그램 또는 claude.ai)를 쓰나요? (y/n)"),
    (r"Claude Code is signed in as (.+)", r"Claude Code 로그인 계정: \1"),
    (r"Claude Code isn't signed in yet\. Run setup again after your first Claude Code session\.", "Claude Code에 아직 로그인하지 않았어요. 처음 Claude Code를 쓴 뒤 설정을 다시 실행하세요."),
    (r"Saved your answers in (.+) \(edit it anytime, or run setup again\)", r"답변을 \1에 저장했어요 (언제든 수정하거나 설정을 다시 실행하세요)"),
    (r"Saved answers in (.+)", r"답변을 \1에 저장했어요"),
    (r"Claude Code hooks and status line", "Claude Code 연결 (훅과 상태 표시줄)"),
    (r"Hooks added to (.+) \(backup saved next to it\)", r"\1에 연결을 추가했어요 (옆에 백업도 저장했어요)"),
    (r"Open Claude Code sessions pick this up after a restart", "열려 있는 Claude Code 세션은 다시 시작해야 적용돼요"),
    (r"You already have a status line \((.*)\)\. Replace it\? \(y/n\)", r"이미 상태 표시줄이 있어요 (\1). 바꿀까요? (y/n)"),
    (r"Kept your status line\. Plan usage \(5-hour / weekly %\) won't show on the board\.", "기존 상태 표시줄을 유지했어요. 보드에 요금제 사용량(5시간/주간 %)은 안 보여요."),
    (r"4\. Apps", "4. 앱"),
    (r"Claude in Chrome", "Chrome의 Claude"),
    (r"Claude account\b", "Claude 계정"),
    (r"Connector added", "커넥터를 추가했어요"),
    (r"Windows: notifications use Windows' own notification center, so nothing to build", "Windows: 알림은 Windows 알림 센터를 써서 따로 만들 게 없어요"),
    (r"The tray buddy starts in the next step; the Chrome tab finder is the last step", "트레이 버디는 다음 단계에서 시작되고, Chrome 탭 찾기는 마지막 단계예요"),
    (r"Xcode command line tools not found, so the app and menu-bar buddy were skipped\.", "Xcode 명령줄 도구가 없어서 앱과 메뉴 막대 버디는 건너뛰었어요."),
    (r"Install them with:  xcode-select --install   then run setup again\.", "설치:  xcode-select --install   그다음 설정을 다시 실행하세요."),
    (r"The board still works in your browser at (\S+)", r"보드는 브라우저에서 \1 로 계속 쓸 수 있어요"),
    (r"Built Agent Board app \(board window \+ notifications\)", "Agent Board 앱을 만들었어요 (보드 창 + 알림)"),
    (r"Built Menu-bar buddy", "메뉴 막대 버디를 만들었어요"),
    (r"Start at login", "로그인할 때 자동 시작"),
    (r"Board server starts at login", "보드 서버가 로그인할 때 시작돼요"),
    (r"Menu-bar buddy starts at login", "메뉴 막대 버디가 로그인할 때 시작돼요"),
    (r"Board server and tray buddy start when you sign in to Windows", "Windows에 로그인하면 보드 서버와 트레이 버디가 시작돼요"),
    (r"Board server and tray buddy started \(tray: bottom-right, next to the clock\)", "보드 서버와 트레이 버디를 시작했어요 (트레이: 오른쪽 아래 시계 옆)"),
    (r"Added “Agent Board” to your Desktop", "바탕화면에 “Agent Board”를 추가했어요"),
    (r"Chrome tab finder \(optional, 3 clicks\)", "Chrome 탭 찾기 (선택, 클릭 3번)"),
    (r"Lets the board find and switch to your Chrome tabs\. It only talks to this computer\.", "보드가 Chrome 탭을 찾고 이동할 수 있게 해요. 이 컴퓨터 안에서만 통신해요."),
    (r"Google Chrome not found, skipping\.", "Google Chrome이 없어서 건너뛰어요."),
    (r"In Chrome, open  chrome://extensions", "Chrome에서  chrome://extensions  를 여세요"),
    (r"Turn on  Developer mode  \(top-right switch\)", "오른쪽 위  개발자 모드  를 켜세요"),
    (r"Click  Load unpacked  and choose this folder:  (.+)", r"압축해제된 확장 프로그램을 로드합니다  를 누르고 이 폴더를 고르세요:  \1"),
    (r"Repeat in each Chrome profile you use \(each Google account has its own extensions\)", "쓰는 Chrome 프로필마다 반복하세요 (Google 계정마다 확장 프로그램이 따로 있어요)"),
    (r"Open Chrome's extensions page and the folder now\? \(y/n\)", "지금 Chrome 확장 프로그램 페이지와 폴더를 열까요? (y/n)"),
    (r"Opened\. When it's loaded, the board's Tabs button shows your tabs\.", "열었어요. 추가가 끝나면 보드의 탭 버튼에서 탭이 보여요."),
    (r"Claude Desktop chats \(connector\)", "Claude 데스크톱 채팅 (커넥터)"),
    (r"Claude Desktop not found, skipping\.", "Claude 데스크톱이 없어서 건너뛰어요."),
    (r"Lets Claude in your Desktop chats show tasks on the board and answer “what are my agents doing\?”\.", "데스크톱 채팅의 Claude가 작업을 보드에 보여 주고 “에이전트들 뭐 하고 있어?”에 답할 수 있어요."),
    (r"Add the Agent Board connector to Claude Desktop\? \(y/n\)", "Claude 데스크톱에 Agent Board 커넥터를 추가할까요? (y/n)"),
    (r"Claude Desktop chats are", "Claude 데스크톱 채팅은"),
    (r"Restart Claude Desktop to load it\. The first time Claude uses it, choose “Always allow”\.", "적용하려면 Claude 데스크톱을 다시 시작하세요. Claude가 처음 쓸 때 “항상 허용”을 고르세요."),
    (r"Claude Desktop connector removed \(restart Claude Desktop\)", "Claude 데스크톱 커넥터를 제거했어요 (Claude 데스크톱 다시 시작)"),
    (r"Done\.(.*) Open (.*)Agent Board(.*) on your Desktop, or (\S+)", r"완료!\1 바탕화면에서 \2Agent Board\3를 열거나 \4 로 접속하세요"),
    (r"Notifications show up from Windows PowerShell; turn them on in Settings → System → Notifications if needed\.", "알림은 Windows PowerShell 이름으로 와요. 필요하면 설정 → 시스템 → 알림에서 켜세요."),
    (r"Restart open Claude Code sessions to load the hooks\.", "열려 있는 Claude Code 세션을 다시 시작해 주세요."),
    (r"macOS may ask to allow notifications from Agent Board, and to let python3 control Google Chrome", "macOS가 Agent Board 알림 허용과 python3의 Google Chrome 제어를 물어볼 수 있어요"),
    (r"\(for the tab finder\)\. Both are optional\.", "(탭 찾기용). 둘 다 선택이에요."),
    (r"Claude Code doesn't seem to be installed yet \(no (.+)\)\. Install it first, then run setup again\.", r"Claude Code가 아직 설치되지 않은 것 같아요 (\1 없음). 먼저 설치한 뒤 설정을 다시 실행하세요."),
]]
LANG = "en"


def tr(text):
    if LANG != "ko":
        return text
    for pat, rep in KO:
        text = pat.sub(rep, text)
    return text


def choose_language(cfg):
    """First question: English or 한국어 (default: the computer's language, or the saved choice)."""
    global LANG
    import i18n
    saved = cfg.get("language")
    default = saved if saved in ("en", "ko") else i18n.system_language()
    a = ask(f"Language / 언어  {D}(1 = English, 2 = 한국어){X}", "2" if default == "ko" else "1")
    LANG = "ko" if a.strip() in ("2", "ko", "한국어", "korean") else "en"
    cfg["language"] = LANG


def say(msg=""): print(tr(msg))
def step(n, title): say(f"\n{B}{n}. {title}{X}")
def ok(msg): say(f"   {G}✓{X} {msg}")
def warn(msg): say(f"   {Y}!{X} {msg}")
def tilde(p): return p.replace(HOME, "~", 1)
def posix(p): return p.replace("\\", "/")
def ask(question, default=""):
    if YES:
        return default
    hint = f" {D}[{default}]{X}" if default else ""
    try:
        a = input(f"   {tr(question)}{hint} ").strip()
    except EOFError:
        a = ""
    return a or default


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
    choose_language(cfg)

    step(1, "Claude in Chrome")
    profs = chrome_profiles()
    cic = dict(cfg.get("claude_in_chrome") or {})
    if not profs:
        warn("Google Chrome not found. Skipping (the Chrome tab finder needs Chrome).")
    for d, (name, email) in profs.items():
        uses = ask(f"Do you use Claude (extension or claude.ai) in {name}? (y/n)", "y" if d in cic else "n").lower().startswith("y")
        if uses:
            cic[d] = {"claude_email": cic.get(d, {}).get("claude_email", "")}
        else:
            cic.pop(d, None)
    cfg["claude_in_chrome"] = cic

    step(2, "Claude account")
    acct = claude_code_account()
    accounts = [a for a in (cfg.get("claude_accounts") or []) if "@" in a]
    if acct:
        if acct not in accounts:
            accounts.insert(0, acct)
        ok(f"Claude Code is signed in as {acct}")
    else:
        warn("Claude Code isn't signed in yet. Run setup again after your first Claude Code session.")
    cfg["claude_accounts"] = accounts

    write(CONFIG, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    ok(f"Saved your answers in {tilde(CONFIG)} (edit it anytime, or run setup again)")
    return cfg


def detect():
    """Everything Claude needs to ask the user the setup questions, as JSON."""
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            current = json.load(fh)
    except (OSError, ValueError):
        current = {}
    chrome = os.path.exists(CHROME_STATE)
    print(json.dumps({
        "os": "windows" if WINDOWS else "macos",
        "python": sys.version.split()[0],
        "project_folder": HERE,
        "settings_folder": AGENT_HOME,
        "claude_code_installed": os.path.isdir(CLAUDE_DIR),
        "claude_account": claude_code_account(),
        "xcode_tools": bool(shutil.which("swiftc")) if not WINDOWS else None,
        "chrome_installed": chrome,
        "claude_desktop_installed": os.path.isdir(DESKTOP_DIR),
        "chrome_extension_folder": EXTENSION_DIR,
        "chrome_extension_steps": [s.format(folder=EXTENSION_DIR) for s in EXTENSION_STEPS],
        "chrome_profiles": [{"dir": d, "name": n, "email": e} for d, (n, e) in chrome_profiles().items()],
        "current_answers": {k: current.get(k) for k in ("language", "claude_in_chrome") if k in current},
    }, indent=2, ensure_ascii=False))


def configure_from(path):
    """Non-interactive version of configure(), from a JSON file of answers."""
    with open(path, encoding="utf-8") as fh:
        a = json.load(fh)
    cfg = {}
    for p in (EXAMPLE, CONFIG):
        try:
            with open(p, encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (OSError, ValueError):
            pass
    if a.get("language") in ("en", "ko", "auto"):
        cfg["language"] = a["language"]
        global LANG
        LANG = "ko" if a["language"] == "ko" else "en"
    if "claude_in_chrome" in a:
        cfg["claude_in_chrome"] = {d: {"claude_email": ""} for d in a["claude_in_chrome"]}
    acct = claude_code_account()
    if acct:
        cfg["claude_accounts"] = [acct] + [x for x in cfg.get("claude_accounts", []) if x != acct and "@" in x]
    write(CONFIG, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    ok(f"Saved answers in {tilde(CONFIG)}")
    return cfg


# ---------------------------------------------------------------- install
# Runs a hook script if it still exists and always exits 0, so a moved or deleted folder never blocks Claude.
WIN_RUNNER = "import os,runpy,sys; p=sys.argv[1]; sys.argv=[p]; os.path.exists(p) and runpy.run_path(p, run_name='__main__')"


def hook_entry(script, **extra):
    p = os.path.join(HERE, "hooks", script)
    if WINDOWS:   # exec form: no shell involved, so it works with Git Bash or PowerShell alike
        return {"type": "command", "command": posix(sys.executable), "args": ["-X", "utf8", "-c", WIN_RUNNER, posix(p)], **extra}
    return {"type": "command", "command": f'f="{p}"; [ -f "$f" ] && python3 "$f"; exit 0', **extra}


def statusline_cmd():
    p = os.path.join(HERE, "hooks", "statusline.py")
    if not WINDOWS:
        return f'f="{p}"; [ -f "$f" ] && python3 "$f" || echo ""'
    py, sc = posix(sys.executable), posix(p)
    git_bash = shutil.which("bash") or os.path.exists(os.path.join(os.environ.get("PROGRAMFILES", ""), "Git", "bin", "bash.exe"))
    return f'"{py}" -X utf8 "{sc}"' if git_bash else f'& "{py}" -X utf8 "{sc}"'


def is_ours(entry):
    text = json.dumps(entry)
    return any(name in text for name in HOOK_SCRIPTS)


def install_hooks():
    step(3, "Claude Code hooks and status line")
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
    notify = hook_entry("notify_hook.py", **{"async": True, "timeout": 20})
    wanted = {
        "Stop": {"hooks": [notify]},
        "Notification": {"hooks": [notify]},
        "PreToolUse": {"matcher": "AskUserQuestion", "hooks": [notify]},
    }
    for event in list(hooks):   # clear any earlier Agent Board entries (including ones no longer used)
        hooks[event] = [e for e in hooks[event] if not is_ours(e)]
        if not hooks[event]:
            del hooks[event]
    for event, entry in wanted.items():
        # Replace an earlier Agent Board entry, keep everything else you already had.
        hooks[event] = [e for e in hooks.get(event, []) if not is_ours(e)] + [entry]
    line = {"type": "command", "command": statusline_cmd(), "padding": 0}
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
    step(4, "Apps")
    if WINDOWS:
        ok("Windows: notifications use Windows' own notification center, so nothing to build")
        warn("The tray buddy starts in the next step; the Chrome tab finder is the last step")
        return False
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


def pythonw():
    w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return w if os.path.exists(w) else sys.executable


def windows_startup():
    """Startup-folder script that runs the board server hidden at login; also starts it now."""
    server = os.path.join(HERE, "server.py")
    tray = ["powershell", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", TRAY]
    vbs = (f'Set sh = CreateObject("WScript.Shell")\r\n'
           f'sh.CurrentDirectory = "{HERE}"\r\n'
           f'sh.Run """{pythonw()}"" -X utf8 ""{server}""", 0, False\r\n'
           f'WScript.Sleep 3000\r\n'
           f'sh.Run "powershell -NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{TRAY}""", 0, False\r\n')
    write(WIN_STARTUP, vbs)
    ok("Board server and tray buddy start when you sign in to Windows")
    if not DRY:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([pythonw(), "-X", "utf8", server], cwd=HERE, creationflags=flags, close_fds=True)
        subprocess.Popen(tray, cwd=HERE, creationflags=flags, close_fds=True)
        ok("Board server and tray buddy started (tray: bottom-right, next to the clock)")


def login_items(apps_built):
    step(5, "Start at login")
    if WINDOWS:
        return windows_startup()
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


def windows_browser():
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
        for rel in (("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe")):
            p = os.path.join(base or "", *rel)
            if base and os.path.exists(p):
                return p
    return None


def windows_shortcut():
    """Desktop shortcut that opens the board in its own Chrome/Edge window (no tabs, no address bar)."""
    exe = windows_browser()
    ps = ("$d=[Environment]::GetFolderPath('Desktop'); "
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Agent Board.lnk')); "
          f"$s.TargetPath='{exe or BOARD}'; " + (f"$s.Arguments='--app={BOARD}'; " if exe else "") +
          "$s.Description='Agent Board'; $s.Save()")
    r = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=False)
    ok("Added “Agent Board” to your Desktop") if r.returncode == 0 else warn(f"Couldn't add the Desktop shortcut: {r.stderr.strip()[:200]}")


def shortcut():
    if WINDOWS:
        return windows_shortcut()
    if not os.path.exists(NOTIFIER_APP) and not DRY:
        return
    if not DRY:
        if os.path.islink(DESKTOP_LINK):
            os.remove(DESKTOP_LINK)
        if not os.path.exists(DESKTOP_LINK):
            os.symlink(NOTIFIER_APP, DESKTOP_LINK)
    ok("Added “Agent Board” to your Desktop")


EXTENSION_STEPS = [
    "In Chrome, open  chrome://extensions",
    "Turn on  Developer mode  (top-right switch)",
    "Click  Load unpacked  and choose this folder:  {folder}",
    "Repeat in each Chrome profile you use (each Google account has its own extensions)",
]


def chrome_extension(interactive=True):
    step(6, "Chrome tab finder (optional, 3 clicks)")
    say(f"   {D}Lets the board find and switch to your Chrome tabs. It only talks to this computer.{X}")
    if not os.path.exists(CHROME_STATE):
        warn("Google Chrome not found, skipping.")
        return
    for i, s in enumerate(EXTENSION_STEPS, 1):
        say(f"   {i}. {s.format(folder=EXTENSION_DIR)}")
    if not interactive or DRY:
        return
    if not ask("Open Chrome's extensions page and the folder now? (y/n)", "y").lower().startswith("y"):
        return
    if WINDOWS:
        exe = windows_browser()
        if exe and "chrome" in exe.lower():
            subprocess.Popen([exe, "chrome://extensions"])
        subprocess.Popen(["explorer", EXTENSION_DIR])
    else:
        subprocess.run(["open", "-a", "Google Chrome", "chrome://extensions"], check=False)
        subprocess.run(["open", EXTENSION_DIR], check=False)
    ok("Opened. When it's loaded, the board's Tabs button shows your tabs.")


def desktop_connector(cfg, wanted=None):
    """Add the Agent Board connector (local MCP server) to Claude Desktop, so chats can report to the board."""
    step(7, "Claude Desktop chats (connector)")
    if not os.path.isdir(DESKTOP_DIR):
        warn("Claude Desktop not found, skipping.")
        return
    say(f"   {D}Lets Claude in your Desktop chats show tasks on the board and answer “what are my agents doing?”.{X}")
    if wanted is None:
        wanted = ask("Add the Agent Board connector to Claude Desktop? (y/n)", "y").lower().startswith("y")
    if not wanted:
        return
    try:
        with open(DESKTOP_CONFIG, encoding="utf-8") as fh:
            dc = json.load(fh)
    except FileNotFoundError:
        dc = {}
    except ValueError:
        warn(f"{tilde(DESKTOP_CONFIG)} isn't valid JSON. Fix it, then run setup again.")
        return
    if os.path.exists(DESKTOP_CONFIG) and not DRY:
        shutil.copy2(DESKTOP_CONFIG, f"{DESKTOP_CONFIG}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    py = posix(sys.executable) if WINDOWS else sys.executable
    dc.setdefault("mcpServers", {})["agent-board"] = {"command": py, "args": ["-X", "utf8", posix(CONNECTOR) if WINDOWS else CONNECTOR]}
    write(DESKTOP_CONFIG, json.dumps(dc, indent=2, ensure_ascii=False) + "\n")
    ok("Connector added")
    say(f"   {D}Restart Claude Desktop to load it. The first time Claude uses it, choose “Always allow”.{X}")


def remove_desktop_connector():
    try:
        with open(DESKTOP_CONFIG, encoding="utf-8") as fh:
            dc = json.load(fh)
    except (OSError, ValueError):
        return
    if (dc.get("mcpServers") or {}).pop("agent-board", None) is not None:
        write(DESKTOP_CONFIG, json.dumps(dc, indent=2, ensure_ascii=False) + "\n")
        ok("Claude Desktop connector removed (restart Claude Desktop)")


def uninstall():
    say(f"{B}Removing Agent Board from Claude Code and login items{X} {D}(your data and config stay){X}")
    remove_desktop_connector()
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
    if WINDOWS:
        if os.path.exists(WIN_STARTUP) and not DRY:
            os.remove(WIN_STARTUP)
        server = os.path.join(HERE, "server.py").replace("'", "''")
        tray = TRAY.replace("'", "''")
        run(["powershell", "-NoProfile", "-Command",
             "$d=[Environment]::GetFolderPath('Desktop'); Remove-Item (Join-Path $d 'Agent Board.lnk') -ErrorAction SilentlyContinue; "
             f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{server}*' -or $_.CommandLine -like '*{tray}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId }}"], check=False)
        ok("Startup item, Desktop shortcut, board and tray buddy removed")
        say(f"   {D}Chrome extension: remove “Agent Board Tabs” in chrome://extensions if you added it.{X}")
        return
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
    if sys.platform not in ("darwin", "win32"):
        sys.exit("Agent Board runs on macOS and Windows.")
    if sys.version_info < (3, 9):
        sys.exit("Please use Python 3.9 or newer.")
    if "--uninstall" in sys.argv:
        return uninstall()
    if "--detect" in sys.argv:
        return detect()
    say(f"\n{B}Agent Board setup{X}  {D}{'(dry run: nothing will change)' if DRY else ''}{X}")
    say(f"{D}A few questions, then everything installs. Press Enter to accept the [default].{X}")
    if not os.path.isdir(CLAUDE_DIR):
        warn(f"Claude Code doesn't seem to be installed yet (no {tilde(CLAUDE_DIR)}). Install it first, then run setup again.")
    if "--answers" in sys.argv:
        global YES
        YES = True
        configure_from(sys.argv[sys.argv.index("--answers") + 1])
    else:
        configure()
    install_hooks()
    built = build_apps()
    login_items(built)
    shortcut()
    chrome_extension(interactive="--answers" not in sys.argv and not YES)
    if "--answers" in sys.argv:
        with open(sys.argv[sys.argv.index("--answers") + 1], encoding="utf-8") as fh:
            a = json.load(fh)
        cfg = json.load(open(CONFIG, encoding="utf-8")) if os.path.exists(CONFIG) else {}
        if a.get("desktop_connector", True):
            desktop_connector(cfg, wanted=True)
    else:
        cfg = json.load(open(CONFIG, encoding="utf-8")) if os.path.exists(CONFIG) else {}
        desktop_connector(cfg, wanted=True if YES else None)
    say(f"\n{G}{B}Done.{X} Open {B}Agent Board{X} on your Desktop, or {BOARD}")
    if WINDOWS:
        say(f"{D}Notifications show up from Windows PowerShell; turn them on in Settings → System → Notifications if needed.")
        say(f"Restart open Claude Code sessions to load the hooks.{X}\n")
        if not DRY:
            time.sleep(2)
            import webbrowser
            webbrowser.open(BOARD)
        return
    say(f"{D}macOS may ask to allow notifications from Agent Board, and to let python3 control Google Chrome")
    say(f"(for the tab finder). Both are optional. Restart open Claude Code sessions to load the hooks.{X}\n")
    if not DRY and os.path.exists(NOTIFIER_APP):
        time.sleep(2)
        subprocess.run(["open", NOTIFIER_APP], check=False)


if __name__ == "__main__":
    main()

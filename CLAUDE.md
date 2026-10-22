# Agent Board — instructions for Claude

Agent Board is a local dashboard of the user's Claude agents (macOS and Windows). It runs only on this
computer at http://127.0.0.1:4317. These are your instructions when working in this folder.

## Privacy rule (always)

- **Never put personal information in this folder**: no project names, folder paths, emails, account names,
  session logs or settings. This folder is code only and may be shared or pushed to a public repository.
- The user's own settings and data live **outside** the project:
  macOS `~/.agent-board/` · Windows `%USERPROFILE%\.agent-board\` (override: `AGENT_BOARD_HOME`).
  `config.json` = their answers, `data/` = logs, trash, usage. Never copy these into the project or commit them.
- Temporary files you create (e.g. an answers file) go in a temp/scratch folder, never in this folder.

## Language

- Talk to the user in **their** language. If they write in Korean, answer in Korean and point them to
  [README.ko.md](README.ko.md).
- Agent Board itself supports English and Korean (board, notifications, menu-bar/tray buddy, setup).
  During setup include `"language": "ko"` (or `"en"`, or `"auto"` = follow the computer) in the answers file.
  Later they can switch in the board: **More ⋯ → Language / 더보기 ⋯ → 언어**.

## When the user asks to install / set up Agent Board

Use `python3` on macOS and `py` on Windows (if `py` is missing, try `python`).

1. **Check requirements** and tell the user plainly what's missing (they must install it themselves):
   - Python 3.9+ (`python3 --version` / `py --version`)
   - Claude Code signed in (the folder `~/.claude` exists and `--detect` shows a `claude_account`)
   - macOS only, recommended: Xcode command line tools (`swiftc --version`; fix: `xcode-select --install`)
   - Optional: Google Chrome (for the Chrome tab finder)
2. **Detect** what's on this computer:
   ```
   python3 setup.py --detect
   ```
   It prints JSON: `os`, `projects` (folders they've used Claude Code in), `chrome_profiles`
   (`dir`, `name`, `email`), `claude_account`, `current_answers`, `chrome_extension_steps`.
3. **Ask the user** (use AskUserQuestion, in their language; short questions, sensible defaults, never guess):
   - **Language** for the board and notifications: English or 한국어 (default: the language they write in).
   - **Personal hours** — default 20:00–08:00. During them the board shows the Personal space and personal
     notifications can arrive; the rest of the day is Work and personal projects are hidden.
   - **Each project folder** from `projects`: Work, Personal, or Skip (skipped ones show as "Unsorted";
     Claude asks again the first time a session starts there).
   - **Each Chrome profile**: Work or Personal (unmarked = Personal), and whether they use Claude
     (extension / claude.ai) in that profile.
   - **Their Claude Code account** (`claude_account`): Work or Personal.
   - If `claude_desktop_installed`: add the **Claude Desktop connector**? (yes by default) and do Desktop
     **chats** count as Work or Personal? (Desktop chat history isn't readable locally; the connector lets Claude
     in their chats report tasks to the board and answer "what are my agents doing?".)
4. **Write the answers** to a temp file outside this folder, in this format (all keys optional):
   ```json
   {
     "language": "ko",
     "personal_hours": {"from": "20:00", "to": "08:00"},
     "projects": {"/Users/kim/code/acme": "work", "/Users/kim/code/blog": "personal"},
     "chrome_profiles": {"Default": "personal", "Profile 1": "work"},
     "claude_in_chrome": ["Default"],
     "claude_account_space": "work",
     "desktop_connector": true,
     "desktop_chats_space": "work"
   }
   ```
   Use the exact `dir` values from `chrome_profiles` and the exact paths from `projects`.
5. **Install**:
   ```
   python3 setup.py --answers <temp-file>
   ```
   Then delete the temp file. Setup keeps the user's existing Claude Code settings (it makes a backup next to
   `settings.json`), adds hooks + status line, starts the board at login, adds a Desktop shortcut, and on macOS
   builds the Agent Board app and menu-bar buddy (Windows: tray buddy).
6. **Tell the user what to do next** (keep it short):
   - Allow the notification prompt (macOS: from "Agent Board"; Windows: from "Windows PowerShell").
   - macOS: allow "python3 wants to control Google Chrome" if asked (tab finder without the extension).
   - **Restart running Claude Code sessions** so they load the hooks.
   - If the connector was added: **restart Claude Desktop**, and choose **Always allow** the first time Claude uses it.
   - Open **Agent Board** on the Desktop.
7. **Offer the Chrome tab finder** (optional): read out `chrome_extension_steps` from `--detect`.
   You cannot install a Chrome extension yourself; the user clicks through `chrome://extensions` →
   Developer mode → Load unpacked → the `extension` folder, once per Chrome profile.

## Other requests

- **Change answers later**: run setup again (`--answers` with only the changed keys, or interactive
  `python3 setup.py`), or edit the config file in the settings folder.
- **Move one project between Work and Personal**: `python3 classify.py <folder> work|personal|unsorted`.
- **Remove it**: `python3 setup.py --uninstall` (keeps the settings folder; tell the user they can delete it).
- **Preview without changes**: `python3 setup.py --dry-run --yes`.

## Troubleshooting

| Symptom | Check / fix |
|---|---|
| Board page won't load | Is the server running? Start it: `python3 server.py`. Logs: macOS `/tmp/com.agent-board.server.log` |
| Board is empty | They haven't used Claude Code since install, or `~/.claude/projects` is empty |
| No notifications | macOS: System Settings → Notifications → Agent Board. Windows: Settings → System → Notifications → Windows PowerShell. Decisions are logged in `<settings folder>/data/notify.log` |
| Personal project shows at work | It's unsorted or marked wrong: `classify.py <folder> personal` |
| No 5-hour / weekly usage | Comes from Claude Code's status line; send one message in Claude Code. If they already had their own status line, setup kept it and usage can't show |
| Tabs button shows a message | Load the Chrome extension (step 7). macOS also works without it via Chrome scripting |

## Code map (for changes)

`server.py` board server + API · `index.html` the board (single page) · `common.py` settings, spaces,
notifications · `cleanup.py` idle agents + trash · `chrome.py` Chrome tabs (extension bridge + macOS scripting) ·
`hooks/` Claude Code hooks + status line · `connector/` Claude Desktop connector (MCP) · `extension/` Chrome extension · `notifier/` macOS app (board window +
notifications) · `menubar/` macOS menu-bar buddy · `tray/` Windows tray buddy · `setup.py` installer.
Before pushing anywhere, check that no personal names, paths or emails were added to tracked files.

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
   It prints JSON: `os`, `chrome_profiles`
   (`dir`, `name`, `email`), `claude_account`, `current_answers`, `chrome_extension_steps`.
3. **Ask the user** (use AskUserQuestion, in their language; short questions, sensible defaults, never guess):
   - **Language** for the board and notifications: English or 한국어 (default: the language they write in).
   - **Each Chrome profile** from `chrome_profiles`: do they use Claude (extension / claude.ai) there?
   - If `claude_desktop_installed`: add the **Claude Desktop connector**? (yes by default) (Desktop chat history isn't readable locally; the connector lets Claude
     in their chats report tasks to the board and answer "what are my agents doing?".)
4. **Write the answers** to a temp file outside this folder, in this format (all keys optional):
   ```json
   {
     "language": "ko",
     "claude_in_chrome": ["Default"],
     "desktop_connector": true
   }
   ```
   Use the exact `dir` values from `chrome_profiles`.
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
- **Theme**: the board has Auto / Light / Dark under **More ⋯ → Theme**.
- **Remove it**: `python3 setup.py --uninstall` (keeps the settings folder; tell the user they can delete it).
- **Preview without changes**: `python3 setup.py --dry-run --yes`.

## Troubleshooting

| Symptom | Check / fix |
|---|---|
| Board page won't load | Is the server running? Start it: `python3 server.py`. Logs: macOS `/tmp/com.agent-board.server.log` |
| Board is empty | They haven't used Claude Code since install, or `~/.claude/projects` is empty |
| No notifications | macOS: System Settings → Notifications → Agent Board. Windows: Settings → System → Notifications → Windows PowerShell. Decisions are logged in `<settings folder>/data/notify.log` |
| No 5-hour / weekly usage | Comes from Claude Code's status line; send one message in Claude Code. If they already had their own status line, setup kept it and usage can't show |
| Tabs button shows a message | Load the Chrome extension (step 7). macOS also works without it via Chrome scripting |

## Code map (for changes)

`server.py` board server + API · `index.html` the board (single page) · `common.py` settings,
notifications · `cleanup.py` idle agents + trash · `chrome.py` Chrome tabs (extension bridge + macOS scripting) ·
`hooks/` Claude Code hooks + status line · `connector/` Claude Desktop connector (MCP) · `extension/` Chrome extension · `notifier/` macOS app (board window +
notifications) · `menubar/` macOS menu-bar buddy · `tray/` Windows tray buddy · `setup.py` installer.
Before pushing anywhere, check that no personal names, paths or emails were added to tracked files.

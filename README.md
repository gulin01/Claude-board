# Agent Board

**English** · [한국어](README.ko.md)

**See all your Claude agents at a glance.** Every Claude Code session (terminal, desktop app, IDE) shows up as a
little animated character: waving = it needs you, typing = working, ✓ = done, sweating = it's grown too big and
should be restarted.

Runs **only on your computer**. Nothing is sent anywhere. Works on **macOS** and **Windows**
(see [Windows](#windows) for what's different there).

> **Easiest: let Claude do it.** Clone the repository, open Claude Code in the folder and say
> *"set up Agent Board for me"*. Claude reads [CLAUDE.md](CLAUDE.md), asks you the questions and installs it.

## Where your information is kept
This folder holds **code only**. Your settings (language, accounts) and data (logs, trash, usage)
live in a separate private folder: **macOS** `~/.agent-board/` · **Windows** `C:\Users\<you>\.agent-board\`.
Nothing is ever sent off your computer, and nothing personal ends up in this folder.

## Start here: setup in 5 minutes

### 1. Check you have these
| Need | How to check | If missing |
|------|--------------|-----------|
| A Mac | | Agent Board is macOS only |
| Claude Code, signed in | `claude --version` | https://docs.anthropic.com/claude-code, then run `claude` once and sign in |
| Python 3.9 or newer | `python3 --version` | `xcode-select --install` (also gives you the next one) |
| Xcode command line tools *(recommended)* | `swiftc --version` | `xcode-select --install`. Needed for the app window, notifications and the menu-bar buddy |
| Google Chrome *(optional)* | | Only for the Chrome tab finder |

### 2. Download it
```bash
git clone -b work https://github.com/gulin01/Claude-board.git ~/agent-board
cd ~/agent-board
```

### 3. Run setup
```bash
python3 setup.py
```
Setup asks your **language** (English / 한국어) and whether you use Claude in each Chrome profile.
Then it installs everything by itself: Claude Code hooks (your existing settings are kept and backed up),
the **Agent Board** app, the menu-bar buddy, start-at-login, and a shortcut on your Desktop.

### 4. Allow two macOS prompts
- **“Agent Board would like to send notifications”** → **Allow**. Tip: System Settings → Notifications →
  Agent Board → **Persistent**, so they stay until you close them.
- **“python3 wants to control Google Chrome”** → **OK** (only for finding your Chrome tabs; it never reads pages).

### 5. Optional: the Chrome tab finder (3 clicks per Chrome profile)
Lets the board find your open Chrome tabs and jump to them. Setup opens the right page and folder for you:
1. In Chrome, open `chrome://extensions`
2. Turn on **Developer mode** (top-right)
3. Click **Load unpacked** and choose the **`extension`** folder inside this project

Do this once in each Chrome profile you use (each Google account has its own extensions). On macOS the tab
finder also works without the extension.

### 6. Optional: Claude Desktop chats (connector)
Claude Desktop's **Chat** conversations aren't stored anywhere the board can read, so setup adds a small
**Agent Board connector** to Claude Desktop. Claude in your chats can then show its tasks on the board
(working → done, with notifications) and answer *"what are my agents doing?"*.

1. **Restart Claude Desktop** so it loads the connector (macOS: ⌘Q, then open it again · Windows: quit it from
   the tray icon, then open it again).
2. **Tell Claude when to report.** Claude Desktop → **Settings → Account → Instructions for Claude**,
   paste this and save:
   ```
   When a request takes several steps (research, writing, planning, coding), use the Agent Board connector:
   call report_progress with status "working" when you start, "done" when you finish (one-line summary),
   and "needs_input" when you need my decision. Skip quick questions and small talk.
   ```
3. **Start a new chat** (the instructions apply to new chats) and check that **Agent Board** is switched on in
   the tools menu (the slider / **+** icon under the message box).
4. **Test it:** ask *"Write a short plan for a team lunch next week."* When Claude asks to use Agent Board,
   choose **Always allow**. A **Desktop · …** tile (▢ badge) appears on the board and a ✅ notification arrives.
5. **Anytime:** ask *"What are my agents doing?"* and Claude reads the board for you.

Old chats and quick questions don't appear: Claude reports tasks, not every message. It only talks to the board
on your computer.

### 7. Restart Claude Code
Close and reopen any running Claude Code sessions so they pick up the new hooks. That's it: open
**Agent Board** on your Desktop. Your agents appear as soon as you use Claude Code.

> Change your answers later: run `python3 setup.py` again (or edit `~/.agent-board/config.json`).
> Preview without changing anything: `python3 setup.py --dry-run`.


## Windows

Same board, characters, usage and longevity. Setup asks the same questions.

### Setup on Windows
1. **Install** (if you don't have them):
   - [Claude Code](https://docs.anthropic.com/claude-code) for Windows, signed in. It also needs
     [Git for Windows](https://git-scm.com/download/win).
   - [Python 3.9+](https://www.python.org/downloads/windows/). In the installer, tick **“Add python.exe to PATH”**.
2. **Download** (in PowerShell):
   ```
   git clone -b work https://github.com/gulin01/Claude-board.git $HOME\agent-board
   cd $HOME\agent-board
   ```
   (Git Bash: `git clone -b work https://github.com/gulin01/Claude-board.git ~/agent-board && cd ~/agent-board`)
3. **Run setup**:
   ```
   py setup.py
   ```
4. **Restart Claude Code** sessions. Open **Agent Board** on your Desktop: it opens in its own Chrome/Edge window.

### What's different on Windows
| | macOS | Windows |
|---|---|---|
| Board, characters, usage, longevity | ✅ | ✅ |
| Notifications (click opens the agent) | ✅ Agent Board app | ✅ Windows notifications (shown as *Windows PowerShell*) |
| Starts at login | ✅ login items | ✅ Startup folder |
| Desktop icon | ✅ Mac app window | ✅ Chrome/Edge app window |
| Buddy next to the clock | ✅ menu bar | ✅ taskbar tray (bottom-right) |
| Chrome tab finder | ✅ with or without the extension | ✅ with the Chrome extension (step 5) |

Notifications not showing? Settings → System → Notifications → turn on **Windows PowerShell**.
Tray buddy hidden? Click the **^** arrow next to the clock and drag the buddy onto the taskbar.
Remove it with `py setup.py --uninstall`.

### Every day
- **Open “Agent Board”** on your Desktop. It starts by itself at login; the board also works at http://127.0.0.1:4317.
- **Tap an agent** to see what it did and act: open its preview, jump to its Chrome tab, resume it, or start fresh.
- **Red battery** = the agent's context is huge, so every message costs more. Finish the task, then tap
  **Fresh start** (copies a summary to paste into a new session) and delete the old one.
- **Menu-bar buddy** next to your clock turns amber and waves when an agent needs you.
- **More ⋯** has TV mode (big characters for a second screen), sounds, trash and more.

### If something doesn't work
| Problem | Fix |
|---------|-----|
| Board is empty | Use Claude Code once, then wait a few seconds. Agents appear by themselves |
| No notifications | System Settings → Notifications → **Agent Board** → Allow. Restart Claude Code sessions |
| No plan usage (5-hour / weekly %) | Send one message in Claude Code; it updates from Claude Code's status line |
| “Starting Agent Board…” stays / page won't load | Run setup again, or start the board by hand: `python3 server.py` (Windows: `py server.py`) |
| Chrome tabs missing | System Settings → Privacy & Security → Automation → python3 → turn on Google Chrome |

### Remove it
```bash
python3 setup.py --uninstall     # removes hooks, login items and the Desktop shortcut; your data stays
```

---

# Reference

In this section `config.json` and `data/` mean the files in your private settings folder
(`~/.agent-board/`, Windows `%USERPROFILE%\.agent-board\`), not this project folder.

## Where the data comes from
- **Claude Code sessions (automatic):** the CLI, the desktop app's Code tab and IDE sessions all write
  transcripts to `~/.claude/projects/`. The board reads them directly, so a new session shows up by itself
  with nothing to install in the agent. Sub-agents are listed under their parent session.
- **Other agents (reported):** Claude in Chrome and other tools don't write local transcripts, so they report here:
  - the **+ Report** button in the dashboard
  - `./report.sh "Chrome · Jira triage" "Moved 4 tickets to In Progress" done acme-app "https://…/jira/…"`
  - `POST /api/event` with `{agent, message, status, project, source, task, url}`

  `url` is the page the agent is working on: the card gets an **Open ↗** link, and clicking its notification opens that page.

  Reports with the same agent name are grouped into one card. Status can be `working`, `done`, `needs_input` or `blocked`.

## Statuses
| Status    | Meaning |
|-----------|---------|
| Working   | The transcript changed in the last 2 min and the turn isn't finished |
| Needs you | The agent asked a question that hasn't been answered yet |
| Your turn | The agent finished its turn within the last 6 h |
| Stalled   | Stopped partway through a turn (a permission prompt, a crash, or it was closed) |
| Idle      | Nothing for more than 6 h |

Environment options: `AGENT_BOARD_PORT` (default 4317) and `AGENT_BOARD_PROJECTS` (default `~/.claude/projects`).


## Notifications
macOS notifications come from Claude Code hooks in `~/.claude/settings.json` (setup adds them).
Notifications come from the small **Agent Board** app in `notifier/` (rebuild with `notifier/build.sh`).
The project name is always first in the title. **Clicking opens the agent** in the Agent Board window,
or, if the agent left a link (a preview, a PR), that page in Chrome.

| Event | Title | Subtitle | Body |
|-------|-------|----------|------|
| Task finished | acme-app · ✅ Done | *task title* | 3 files changed · Step 1 is done and committed. |
| Needs input | acme-app · ⏳ Needs you | *task title* | Needs your permission to use Bash |
| Question | acme-app · ❓ Question | *task title* | *the question* |
| Idle 24h | acme-app · 💤 2 idle agents | *their titles* | Unused for 24h+ · click to keep or delete |

To keep notifications on screen until you close them: System Settings → Notifications → **Agent Board**
→ set the style to **Persistent** (Alerts). The browser is `browser` in `config.json` (empty = default browser).

- Every finished task, question or permission prompt notifies you.
- Reported agents (report.sh / + Report) notify when their status is `done`, `needs_input` or `blocked`.
- Every decision is logged in `data/notify.log` (SENT / SKIP with the reason).

To change the sound (`Glass`, `Ping`, `Hero`…), edit `config.json`.
To turn notifications off, remove the `hooks` block from `~/.claude/settings.json`.
If no banners appear: System Settings → Notifications → **Agent Board** → Allow notifications.

## Idle agents (24 h cleanup)
Every 30 minutes the board looks for agents with no activity for `stale_after_hours` (24).
- You get **one** grouped notification, e.g. "💤 2 idle agents · Unused for 24h+ · keep or delete on Agent Board".
  Each agent is only mentioned once per idle stretch.
- The board shows a **💤 Idle for 24h+** panel with **Keep** (stop asking until it's used and goes idle again)
  and **Delete**.
- **Delete** moves the session's files into `data/trash/`. It disappears from the board and from `claude --resume`.
  Use **🗑 → Restore** to bring it back, or **Empty trash** to remove it permanently.
- Desktop-app sessions also live in the app's sidebar, so for those the button is **Hide**. Delete them in the app.

## Auto-start
Setup adds two login items: `com.agent-board.server` (the board) and `com.agent-board.menubar` (menu-bar buddy),
in `~/Library/LaunchAgents/` (logs in `/tmp/com.agent-board.*.log`).

    launchctl kickstart -k gui/$(id -u)/com.agent-board.server                           # restart after editing code
    launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.agent-board.server.plist   # stop / disable

## Longevity (when to start a fresh agent)
A long-running agent re-reads its whole context on every message, so it gets slower and costlier over time.
Each card shows one square per day since the agent started (filled = used that day), plus `Day N` and its
current context size. Days after `fresh_days` (2) turn **red**, as does a context over `context_warn_k` (250k).
Those agents get a **Start fresh** tag and are counted in the "Start fresh" tile (click it to filter).
Open the card → **Copy handoff for a new agent** copies a short brief (task, where it left off, files)
to paste into a new Claude session, then delete the old one.

## Links from agents
URLs in an agent's final message (local previews, PRs, tickets) show on its card as **↗** links.
When it finishes, clicking the notification opens the first link; **View on board** opens its card.

## Claude tabs (Chrome)
The **Claude tabs** view shows the Chrome tabs your Claude agents are using. Click one to jump to it.
- **Active** (default): tabs of agents that are working now or used Chrome in the last 30 minutes.
  **All Claude tabs**: every tab an agent used. **All tabs**: everything open (incognito excluded).
- How a tab is matched to an agent: pages a Claude Code agent opened with Claude in Chrome (from its log),
  links in its final message, and the `url` a reported agent sent.
- Agents in the **Claude extension's side panel** don't leave anything on your Mac the board can read, so they
  must report their tab: **+ Report → Connect Chrome agents → Copy instructions** and paste that into your
  Claude in Chrome instructions. They then open `http://127.0.0.1:4317/report?agent=…&status=…&message=…&url=…`,
  which pre-fills the report; saving still takes a click, so other websites can't post fake reports.
- Agent links on cards and in notifications switch to the already-open tab instead of opening a duplicate.

- Each tab shows which **Chrome profile / Google account** it belongs to, and you can filter by account.
  (Matched via the window ids in each profile's `Sessions/` file; Chrome doesn't expose this to scripts.)

Uses macOS scripting of Chrome (System Settings → Privacy & Security → Automation → python3 → Google Chrome).
Reads only tab titles and addresses, never page contents, and never closes tabs.

## Usage panel (always visible)
On wide screens a panel stays pinned on the right; on narrow ones it becomes pills under the header.
- **Claude plan usage**: your real 5-hour and weekly limit %, with reset times. Claude Code hands these to its
  status line; `hooks/statusline.py` (set as `statusLine` in `~/.claude/settings.json`) saves them to
  `data/usage.json` and also shows `project · Day N · context · 5h % · week %` in every Claude Code terminal.
  They refresh whenever a Claude Code session gets a message, and are kept **per Claude account**
  (from the logged-in account in `~/.claude.json`), so two accounts get two sets of meters.
  Usage of accounts used only in the Chrome extension or claude.ai isn't available locally.
- **Tokens processed**: today / last 5 h / 7 days, with a 7-day bar chart and the heaviest agents today.
  Includes context re-reads and sub-agents, which is why long agents dominate.
- **Longevity**: agents to restart (Day N / context), and **Active now**. Every row jumps to its card.

## Claude accounts & claude.ai tabs
- `claude_accounts` in `config.json` lists your Claude accounts. Ones used in Claude Code get live meters;
  Chrome-only ones (extension, Claude Design) get **Open usage ↗**, which opens claude.ai's usage page in the
  Chrome profile signed in with the same email.
- claude.ai tabs count as Claude tabs and are labelled **Claude Design** / **Claude chat**. The side panel's
  **Claude in Chrome** box lists them per account; click one to jump to it.

## Board 2.0
- **Characters:** every agent is a buddy whose mood shows its status: waving = needs you, typing = working,
  happy ✓ = done, sweating = tired (too old or too big, start fresh), ? = stuck, asleep = unused 24h.
  Battery = context size, squares = days alive, badge = where it runs (>_ terminal, ▢ desktop app, ◎ Chrome).
- **Now bar:** tap a counter to highlight those agents; tap the usage rings for usage details.
- **Rooms:** one room per project, plus Chrome (claude.ai tabs) and the Sleep corner.
- **Theme:** More ⋯ → Theme: Auto (follow the computer), Light or Dark.
- **Tap an agent** for its details panel: counts, one-line update, Open / Jump to tab / Resume / Fresh start / Delete.
- **Alive:** tool bubbles as agents work, confetti when one finishes, an activity river at the bottom.
  Sounds (off by default) and the river are in **More**.
- **TV mode** (More → TV mode, or `#tv`): full screen, big characters, for a second monitor.
- **Menu-bar buddy:** `menubar/build.sh` builds it; it starts at login via
  `~/Library/LaunchAgents/com.agent-board.menubar.plist`. Amber and waving = someone needs you.


## The Agent Board app
`notifier/Agent Board.app` is both the notification sender and the board window. Open it (Desktop shortcut
`~/Desktop/Agent Board.app`, Dock, Spotlight) and the board opens in its own window, running only on this Mac.
Board links stay in the window; other links open in Chrome (switching to the tab if it's open). Clicking a
notification opens that agent in the window. Rebuild with `notifier/build.sh` after changing `main.swift`.

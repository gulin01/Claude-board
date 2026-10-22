# Agent Board 2.0 — build checklist

Plan: `design/plan.html` (published: https://claude.ai/artifact/XeLWtFBLfTuMZidYTsxPpF).
To resume after a restart: open Claude Code in this folder and say "continue the build";
work through the first unchecked item. Commit after each checked item.

## Step 1 · New look
- [x] Server: per-agent counts (files, commands, pages, helpers) for the details panel
- [x] New palette, fonts and the buddy character (6 moods + where-it-runs badge)
- [x] Now bar: needs you / working / done / asleep counters (tap to filter) + usage rings per account
- [x] Rooms: Work, Personal, Unsorted (with sort buttons), Chrome (claude.ai tabs)
- [x] Tiles: buddy, short name, project dot, battery (context), day squares
- [x] Details panel: counters, one-sentence update, big buttons, "More" with full log
- [x] Sleep corner: idle 24h+ with Keep / Delete, trash
- [x] More menu: report, digest, trash, tabs finder, range, scratch sessions
- [x] Deep links from notifications (#s=<id>, #idle) open the right panel
- [x] Check desktop + phone widths, light + dark; commit

## Step 2 · Alive
- [x] Live tool bubbles from new timeline entries
- [x] Done celebration + optional sound
- [x] Activity river

## Step 3 · Everywhere
- [x] Menu-bar buddy (native)
- [x] TV mode

## Spaces · Work and Personal kept apart
- [x] Server: current space (auto by hours, manual until next 8:00/20:00), /api/space
- [x] Server: sessions, tabs, usage, trash and summary only return the current space
- [x] Chrome profiles and Claude accounts mapped to spaces (config)
- [x] Notifications: personal allowed in personal hours or when Personal space is on
- [x] Board: Work | Personal switch, rooms per space, river reset, 10-min privacy guard
- [x] Menu-bar buddy: shows current space, can switch
- [x] Check and commit

## Windows extras · tab finder + tray buddy
- [x] Server: WebSocket bridge for the Chrome extension (/ws/tabs), pinned extension id only
- [x] Chrome extension: reports tabs per profile, switches/opens tabs on request (works on Mac too)
- [x] chrome.py uses extension data when fresh; AppleScript stays as the Mac fallback
- [x] Windows tray buddy (PowerShell, no installs): mood icon, list, space switch, open board
- [x] setup.py: start tray at sign-in, open chrome://extensions + folder; README steps
- [x] Test (Mac + simulated), commit, push

## Language · English / 한국어
- [x] Setting: language (auto/en/ko) in settings, /api/settings, sent to board + summary
- [x] Notifications + idle reminders translated
- [x] Board: all labels translated, Language menu
- [x] Tray (Windows) + menu-bar buddy (Mac) use labels from the server
- [x] setup.py asks language first and speaks it; README.ko.md; CLAUDE.md language note
- [x] Test both languages, commit, push

## Claude Desktop chats · connector
- [ ] connector/agent_board_mcp.py: stdio MCP server (stdlib), tools report_progress + list_agents
- [ ] Server: Desktop chats get their own space setting (desktop_chats_space); ▢ badge
- [ ] setup.py: add/remove the connector in claude_desktop_config.json (Mac + Windows), ask the space
- [ ] Test with a simulated Claude Desktop, install on this Mac, README/CLAUDE.md, commit, push

## Step 4 · Product
- [ ] One-click setup, settings screen, EN / 한국어 / O'zbek, Mac app

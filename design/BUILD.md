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

## Step 4 · Product
- [ ] One-click setup, settings screen, EN / 한국어 / O'zbek, Mac app

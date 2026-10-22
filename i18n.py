"""Language: "auto", "en" or "ko" (setting `language` in config.json).

"auto" follows the computer's language (Korean if the system's first language is Korean, else English).
The board page has its own copy of its labels (index.html); this file covers notifications and the
menu-bar / tray buddies, which get their labels from /api/summary.
"""
import os
import re
import subprocess
import sys

LANGS = ("en", "ko")

STRINGS = {
    "en": {
        # notifications
        "done": "✅ Done", "needs_you": "⏳ Needs you", "question": "❓ Question", "blocked": "⏳ Blocked",
        "finished": "Finished", "has_question": "Has a question for you",
        "files_changed": "{n} file changed", "files_changed_pl": "{n} files changed",
        "permission": "Needs your permission to use {tool}",
        "idle_one": "💤 1 idle agent", "idle_many": "💤 {n} idle agents",
        "idle_body": "Unused for 24h+ · click to keep or delete",
        "session": "Claude session", "no_folder": "No folder",
        # menu-bar / tray buddy
        "needs_you_list": "Needs you", "working_list": "Working",
        "n_done": "{n} done", "n_restart": "{n} to restart", "n_asleep": "{n} asleep",
        "n_need_you": "{n} need you", "n_working": "{n} working", "all_quiet": "all quiet",
        "open_board": "Open Agent Board", "quit": "Quit", "not_running": "Agent Board isn't running",
        "five_hour": "5h", "week": "week",
    },
    "ko": {
        "done": "✅ 완료", "needs_you": "⏳ 확인 필요", "question": "❓ 질문", "blocked": "⏳ 막힘",
        "finished": "작업을 마쳤어요", "has_question": "질문이 있어요",
        "files_changed": "파일 {n}개 변경", "files_changed_pl": "파일 {n}개 변경",
        "permission": "{tool} 사용 권한이 필요해요",
        "idle_one": "💤 쉬고 있는 에이전트 1개", "idle_many": "💤 쉬고 있는 에이전트 {n}개",
        "idle_body": "24시간 넘게 사용 안 함 · 눌러서 유지하거나 삭제",
        "session": "Claude 세션", "no_folder": "폴더 없음",
        "needs_you_list": "확인 필요", "working_list": "작업 중",
        "n_done": "{n}개 완료", "n_restart": "{n}개 새로 시작 필요", "n_asleep": "{n}개 잠듦",
        "n_need_you": "{n}개 확인 필요", "n_working": "{n}개 작업 중", "all_quiet": "모두 조용해요",
        "open_board": "Agent Board 열기", "quit": "종료", "not_running": "Agent Board가 실행 중이 아니에요",
        "five_hour": "5시간", "week": "주간",
    },
}

_system = None


def system_language():
    """'ko' if the computer's preferred language is Korean, else 'en'. Cached per process."""
    global _system
    if _system:
        return _system
    lang = ""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r'"?([a-zA-Z]{2})[-_"]', out)
            lang = m.group(1) if m else ""
        elif sys.platform == "win32":
            import ctypes
            lang = "ko" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x12 else "en"
    except Exception:
        pass
    lang = lang or (os.environ.get("LANG") or "en")[:2]
    _system = "ko" if lang.lower() == "ko" else "en"
    return _system


def resolve(setting):
    return setting if setting in LANGS else system_language()


def language(cfg=None):
    if cfg is None:
        import common
        cfg = common.load_config()
    return resolve(cfg.get("language", "auto"))


def t(key, lang=None, **kw):
    lang = lang or language()
    text = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**kw) if kw else text


def files_changed(n, lang=None):
    return t("files_changed" if n == 1 else "files_changed_pl", lang, n=n)


def permission_message(msg, lang=None):
    """Claude Code's permission notices arrive in English; translate the common one."""
    m = re.search(r"permission to use (\S+)", msg or "")
    if m:
        return t("permission", lang, tool=m.group(1))
    return (msg or "").replace("Claude needs your", "Needs your")


def labels(lang=None):
    """Labels for the menu-bar / tray buddy."""
    lang = lang or language()
    keys = ("needs_you_list", "working_list",
            "n_done", "n_restart", "n_asleep", "n_need_you", "n_working", "all_quiet", "open_board", "quit",
            "not_running", "five_hour", "week")
    return {k: t(k, lang) for k in keys}

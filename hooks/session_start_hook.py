#!/usr/bin/env python3
"""Claude Code SessionStart hook: in a project that isn't sorted yet, have Claude ask
whether it's a work or personal project, then record the answer with classify.py."""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import common  # noqa: E402


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    cwd = data.get("cwd") or ""
    if not common.needs_classification(cwd):
        return
    classify = os.path.join(HERE, "classify.py")
    context = (
        "Agent Board setup: this folder is not yet sorted as a work or personal project. "
        "Before starting on the user's request, ask them one question with AskUserQuestion: "
        f"\"Is {os.path.basename(cwd)} a work or personal project?\" with the options "
        "\"Work\" (notifications any time) and \"Personal\" (notifications only 8 pm–8 am). "
        f"Then record the answer by running: \"{sys.executable}\" \"{classify}\" \"{cwd}\" work   (or personal). "
        "Mention the choice in one short line, then continue with the request."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        try:
            common.log(f"ERROR session_start_hook: {ex!r}")
        except Exception:
            pass
    sys.exit(0)

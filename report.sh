#!/bin/sh
# Report progress to Agent Board from any script or agent.
# Usage: ./report.sh "<agent name>" "<what was done>" [working|done|needs_input|blocked] [project] [url]
#   url: the page the agent is on (e.g. its Chrome tab); clicking the notification opens it.
agent="$1"; msg="$2"; status="${3:-working}"; project="${4:-}"; url="${5:-}"
python3 - "$agent" "$msg" "$status" "$project" "$url" <<'PY'
import json, sys, urllib.request
a, m, s, p, u = sys.argv[1:6]
body = json.dumps({"agent": a, "message": m, "status": s, "project": p or None, "url": u or None,
                   "source": "report.sh"}).encode()
req = urllib.request.Request("http://127.0.0.1:4317/api/event", body, {"content-type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
PY

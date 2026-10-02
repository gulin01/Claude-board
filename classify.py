#!/usr/bin/env python3
"""Sort a project folder as work or personal.

  python3 classify.py <folder> work|personal|unsorted
  python3 classify.py --list
"""
import sys

import common

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        for path, cat in sorted(common.load_config()["projects"].items()):
            print(f"{cat:9} {path}")
    elif len(sys.argv) == 3:
        key = common.set_category(sys.argv[1], sys.argv[2].lower())
        print(f"Saved: {key} → {sys.argv[2].lower()}")
    else:
        print(__doc__.strip())
        sys.exit(1)

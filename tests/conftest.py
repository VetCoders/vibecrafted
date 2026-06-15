import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
repo_root_str = str(REPO_ROOT)

if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

os.environ.setdefault("VIBECRAFTED_MARBLES_PROBE_NOTIFY", "0")
os.environ.setdefault("VIBECRAFTED_TEST_ALLOW_NON_TTY_VC_FRAME", "1")

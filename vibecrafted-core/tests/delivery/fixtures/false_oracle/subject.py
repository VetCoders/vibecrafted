import pathlib
import sys

pathlib.Path(sys.argv[1]).write_text("verified-value\n", encoding="utf-8")

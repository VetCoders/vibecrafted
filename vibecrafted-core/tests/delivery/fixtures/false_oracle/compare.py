import pathlib
import sys

oracle = pathlib.Path(sys.argv[1]).read_bytes()
golden = pathlib.Path(sys.argv[2]).read_bytes()
raise SystemExit(0 if oracle == golden else 1)

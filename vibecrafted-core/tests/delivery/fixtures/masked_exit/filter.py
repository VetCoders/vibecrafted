import sys

payload = sys.stdin.read()
sys.stdout.write(payload)
raise SystemExit(0)

"""Python canary plugin metadata (prompt hints; CLI uses snapshot tags)."""

GLOBS = ("*.py",)
KIND_ENUM = ("def", "class", "module")
COMPILE = "python3 -m py_compile {files}"
LINT = "ruff check {files}"
DOC_STYLE = "PEP 257; 1–3 lines; no argument restating the name"

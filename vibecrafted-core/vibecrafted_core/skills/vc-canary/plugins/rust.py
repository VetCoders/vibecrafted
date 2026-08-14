"""Rust canary plugin — catalog schema is strict (codescribe field lesson)."""

GLOBS = ("*.rs",)
KIND_ENUM = ("fn", "struct", "enum", "mod", "trait", "impl", "const", "type", "module")
# role + authority REQUIRED on every catalog unit or settle rejects the scope
REQUIRED_FIELDS = (
    "file",
    "name",
    "line",
    "kind",
    "role",
    "docstring_added",
    "authority",
)
COMPILE = "CODESCRIBE_NO_EMBED=1 cargo check -p {crate}"  # operator fills crate
LINT = "cargo clippy -p {crate} -- -D warnings"
DOC_STYLE = "/// rustdoc; no doc-comments glued between #[derive] blocks"

from __future__ import annotations

VAPOR_HEADER = "\uff36\uff49\uff42\uff45\uff43\uff52\uff41\uff46\uff54\uff45\uff44"
MONO_SUB = (
    "\U0001d69f\U0001d692\U0001d68b\U0001d68e\U0001d68c"
    "\U0001d69b\U0001d68a\U0001d68f\U0001d69d"
)
MONO_CLI = "\U0001d69f\U0001d68c-\U0001d68c\U0001d695\U0001d692"
FRAMEWORK_STAMP = (
    "\U0001f175\u00b7\U0001f141\u00b7\U0001f130\u00b7\U0001f13c"
    "\u00b7\U0001f134\u00b7\U0001f146\u00b7\U0001f15e\u00b7\U0001f161\u00b7\U0001f17a"
)
TAGLINE = "The Founders' Framework"
PRODUCT_LINE = "A convergence-driven system for shipping software with AI agents."
FOOTER_BRANDING = "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents (c)2024-2026 VetCoders"


def version_line(version: str) -> str:
    return f"{MONO_SUB} ({MONO_CLI}) \U0001d69f{version}"


def separator(width: int = 57) -> str:
    return "\u2500" * max(24, width)

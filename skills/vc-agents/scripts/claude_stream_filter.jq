# Claude Code stream-json → clean readable terminal output
# Events: system, assistant, user, stream_event, result, rate_limit_event

def stamp: (now | strftime("%H:%M:%S"));
def tool_tag($name): "\u001b[36m[" + stamp + " " + $name + "]\u001b[0m ";

# Assistant messages — full text blocks (the meat)
if .type == "assistant" then
  (.message.content[]? |
    if .type == "text" then "\n" + .text + "\n"
    elif .type == "thinking" then "\n\u001b[2m" + (.thinking // "") + "\u001b[0m\n"
    elif .type == "tool_use" then tool_tag(.name)
    else empty end
  ) // empty

# Stream deltas — live text as it arrives
elif .type == "stream_event" then
  (.event // {}) as $e |
  if $e.type == "content_block_delta" then
    if $e.delta.type == "text_delta" then $e.delta.text
    elif $e.delta.type == "thinking_delta" then "\u001b[2m" + ($e.delta.thinking // "") + "\u001b[0m"
    else empty end
  elif $e.type == "content_block_start" and $e.content_block.type == "tool_use" then
    "\n" + tool_tag($e.content_block.name // "?")
  else empty end

# Result — final output
elif .type == "result" then
  "\n\u001b[32m[" + stamp + "] " + (.result // "done") + "\u001b[0m\n"

# Session init
elif .type == "system" and .subtype == "init" then
  "\u001b[33m[" + stamp + "] session: " + .session_id + "\u001b[0m\n"

else empty end

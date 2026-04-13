# Gemini CLI stream-json filter
# Handles both legacy format (type=message, tool_use, tool_result)
# and Gemini 3.1 format (type=gemini with thoughts[] + toolCalls[])
# Verified against real output 2026-03-27 (legacy) + 2026-04-12 (3.1)

def stamp: (now | strftime("%H:%M:%S"));
def tool_tag($name): "\u001b[36m[" + stamp + " " + $name + "]\u001b[0m ";

# Helper: emit thoughts array as dimmed reasoning lines
def emit_thoughts:
  ((.thoughts // [])[] |
    "\u001b[2m[" + stamp + " thinking] " + (.subject // "?") + ": " + (.description // "") + "\u001b[0m\n"
  );

if .type == "init" then
  "\u001b[33m[" + stamp + "] session: " + (.session_id // "?") + "\u001b[0m"
  + (if .model then " (" + .model + ")" else "" end) + "\n"

# Gemini 3.1 format: type=gemini with thoughts, content, toolCalls
elif .type == "gemini" then
  # Emit thoughts as reasoning
  emit_thoughts,
  # Emit content if non-empty
  (if (.content // "") != "" then .content else empty end),
  # Emit tool calls
  ((.toolCalls // [])[] |
    "\n" + tool_tag(.name // "?")
  )

# Legacy format: type=message with role=assistant
elif .type == "message" then
  if .role == "assistant" then
    # Support thoughts on legacy message events too (hybrid format)
    emit_thoughts,
    (if (.content // "") != "" then .content else empty end)
  else empty end

elif .type == "tool_use" then
  "\n" + tool_tag(.tool_name // .name // "?")

elif .type == "tool_result" then
  (.output // "") as $out |
  if ($out | length) > 0 then
    ($out | split("\n")) as $lines |
    if ($lines | length) > 12 then
      "\u001b[2m" + ($lines[0:5] | join("\n")) + "\n  ... (" + ($lines | length | tostring) + " lines)\u001b[0m\n"
    elif ($out | length) > 500 then
      "\u001b[2m" + $out[0:400] + " ...\u001b[0m\n"
    else
      "\u001b[2m" + $out + "\u001b[0m\n"
    end
  else empty end

elif .type == "error" then
  "\u001b[31m[" + stamp + " error] " + (.message // .error // "unknown") + "\u001b[0m\n"

elif .type == "result" then
  "\n\u001b[32m[" + stamp + "] " + (.status // "done") + "\u001b[0m"
  + (if .stats then
      " \u001b[2m" + (.stats.input_tokens | tostring) + " in / "
      + (.stats.output_tokens | tostring) + " out"
      + " / " + (.stats.duration_ms | tostring) + "ms"
      + (if .stats.tool_calls then " / " + (.stats.tool_calls | tostring) + " tools" else "" end)
      + "\u001b[0m"
    else "" end)
  + "\n"

else empty end

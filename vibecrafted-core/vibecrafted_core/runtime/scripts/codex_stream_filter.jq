# Codex JSONL stream filter
# Converts structured --json events to readable terminal output
# Event types: thread.started, turn.started/completed/failed, item.started/completed

def stamp: (now | strftime("%H:%M:%S"));
def tool_tag($name): "\u001b[36m[" + stamp + " " + $name + "]\u001b[0m";
def stringish:
  if . == null then ""
  elif type == "string" then .
  elif type == "number" or type == "boolean" then tostring
  elif type == "object" then (.message // .error // .detail // tojson)
  elif type == "array" then map(
    if type == "string" then .
    elif type == "number" or type == "boolean" then tostring
    else tojson
    end
  ) | join(", ")
  else tostring
  end;

if .type == "thread.started" then
  "\u001b[33m[" + stamp + "] session: " + (.thread_id // "?") + "\u001b[0m\n"

elif .type == "item.started" then
  (.item // {}) as $i |
  if $i.type == "command_execution" then
    "\n" + tool_tag("$ " + ($i.command // "cmd")) + "\n"
  elif $i.type == "mcp_tool_call" then
    tool_tag(($i.server // "") + ":" + ($i.tool // $i.name // "?")) + " "
  elif $i.type == "web_search" then
    tool_tag("search") + " "
  elif $i.type == "plan_update" then
    "\u001b[35m[" + stamp + " plan]\u001b[0m "
  else empty end

elif .type == "item.completed" then
  (.item // {}) as $i |
  if $i.type == "agent_message" then
    "\n" + ($i.text // "") + "\n"
  elif $i.type == "reasoning" then
    "\u001b[2m" + ($i.text // "") + "\u001b[0m\n"
  elif $i.type == "command_execution" then
    ($i.output // "") as $out |
    if ($out | length) > 0 then
      ($out | split("\n")) as $lines |
      if ($lines | length) > 12 then
        "\u001b[2m" + ($lines[0:5] | join("\n")) + "\n  ... (" + ($lines | length | tostring) + " lines)\u001b[0m\n"
      else
        "\u001b[2m" + $out + "\u001b[0m\n"
      end
    else empty end
  elif $i.type == "mcp_tool_call" then
    # MCP results have nested content; show truncated
    ($i.result.content[0].text // "") as $out |
    if ($out | length) > 0 then
      ($out | split("\n")) as $lines |
      if ($lines | length) > 12 then
        "\u001b[2m" + ($lines[0:5] | join("\n")) + "\n  ... (" + ($lines | length | tostring) + " lines)\u001b[0m\n"
      else empty end
    else empty end
  elif $i.type == "file_changes" then
    "\u001b[32m[" + stamp + " write: " + ($i.path // "?") + "]\u001b[0m\n"
  else empty end

elif .type == "turn.completed" then
  (.usage // {}) |
  if .input_tokens then
    "\n\u001b[2m[" + stamp + "] tokens: " + (.input_tokens | tostring) + " in"
    + (if .cached_input_tokens then " (" + (.cached_input_tokens | tostring) + " cached)" else "" end)
    + " / " + (.output_tokens | tostring) + " out\u001b[0m\n"
  else empty end

elif .type == "turn.failed" then
  "\n\u001b[31m[" + stamp + " error] "
  + ((.error // .message // "turn failed") | stringish)
  + "\u001b[0m\n"

else empty end

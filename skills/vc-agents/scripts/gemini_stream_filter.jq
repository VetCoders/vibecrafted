# Gemini CLI stream-json filter
# Converts --output-format stream-json events to readable terminal output
# Event types: init, message, tool_use, tool_result, error, result

def stamp: (now | strftime("%H:%M:%S"));
def tool_tag($name): "\u001b[36m[" + stamp + " " + $name + "]\u001b[0m ";

if .type == "init" then
  "\u001b[33m[" + stamp + "] session: " + (.session_id // .id // "?") + "\u001b[0m"
  + (if .model then " (" + .model + ")" else "" end) + "\n"

elif .type == "message" then
  # Message chunks — extract text from content or direct text field
  (.content // .text // .delta // null) as $body |
  if ($body | type) == "string" then
    $body
  elif ($body | type) == "array" then
    ($body[] |
      if (type) == "string" then .
      elif .type == "text" then (.text // .delta // "")
      elif .type == "thinking" then "\u001b[2m" + (.text // .thinking // "") + "\u001b[0m"
      else empty end
    ) // empty
  else empty end

elif .type == "tool_use" then
  "\n" + tool_tag(.name // .tool // "?")

elif .type == "tool_result" then
  (.output // .content // .text // "") as $out |
  if ($out | type) == "string" and ($out | length) > 0 then
    ($out | split("\n")) as $lines |
    if ($lines | length) > 12 then
      "\u001b[2m" + ($lines[0:5] | join("\n")) + "\n  ... (" + ($lines | length | tostring) + " lines)\u001b[0m\n"
    elif ($out | length) > 500 then
      "\u001b[2m" + $out[0:400] + " ...\u001b[0m\n"
    else empty end
  else empty end

elif .type == "error" then
  "\u001b[31m[" + stamp + " error] " + (.message // .error // .text // "unknown error") + "\u001b[0m\n"

elif .type == "result" then
  "\n\u001b[32m[" + stamp + "] " + (.text // .result // "done") + "\u001b[0m\n"
  + (if .usage then
      "\u001b[2m[" + stamp + "] tokens: " + ((.usage.input_tokens // .usage.prompt_tokens // 0) | tostring) + " in"
      + " / " + ((.usage.output_tokens // .usage.completion_tokens // 0) | tostring) + " out\u001b[0m\n"
    else "" end)

else empty end

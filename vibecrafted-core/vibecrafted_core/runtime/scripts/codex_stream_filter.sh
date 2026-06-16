#!/usr/bin/env bash
# Codex output cleaner — removes tool result noise while preserving agent text
# Filters: ERROR loader lines, massive JSON search results, raw grep dumps
# Keeps: agent reasoning, commands, file edits, summaries

awk '
  # Detect JSON search result dumps (many "file": + "context": on one line)
  # These are tool outputs from search_tool_bm25 or grep
  {
    # Count "file": occurrences — if > 3 on one line, it is tool dump
    n = gsub(/"file":/, "&")
    if (n > 3) {
      # Print a short summary instead of the wall
      printf "\033[2m  [search: %d results]\033[0m\n", n
      next
    }
  }

  # Detect escaped JSON blobs (\"file\": pattern from codex internal format)
  {
    m = gsub(/\\"file\\":/, "&")
    if (m > 3) {
      printf "\033[2m  [search: %d results]\033[0m\n", m
      next
    }
  }

  # Pass everything else through
  { print }
'

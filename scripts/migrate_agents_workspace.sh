#!/usr/bin/env bash
set -euo pipefail

# Skrypt migracyjny dla legacy katalogów z `.ai-agents/`
# Wykonuje "twardą" przeprowadzkę legacy katalogów z `.ai-agents/`
# do centralnego archiwum $VIBECRAFTED_ROOT/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/
# Przenosi wyłącznie foldery: plans, pipeline, reports, tmp
# Pozostawia nietknięte ewentualne inne pliki w .ai-agents/ (np. GUIDELINES.md)
#
# Użycie:
#   ./migrate_agents_workspace.sh [--dry-run] [dir1 dir2 ...]
#   Domyślnie przeszukuje $VIBECRAFTED_ROOT/ albo bieżący katalog
#
# Do weryfikacji org/repo można też użyć: zsh -ic 'repo-full'

default_vibecrafted_home() {
  if [[ -n "${VIBECRAFTED_HOME:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_HOME"
    return
  fi
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_ROOT/.vibecrafted"
    return
  fi
  printf '%s\n' "$HOME/.vibecrafted"
}

default_search_root() {
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_ROOT/"
    return
  fi
  printf '%s\n' "$PWD"
}

VIBECRAFTED_HOME="$(default_vibecrafted_home)"
DEFAULT_SEARCH_ROOT="$(default_search_root)"

# Parsowanie argumentów: pierwszy arg może być --dry-run, reszta to katalogi
DRY_RUN=""
SEARCH_DIRS=()
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
  else
    SEARCH_DIRS+=("$arg")
  fi
done
[[ ${#SEARCH_DIRS[@]} -eq 0 ]] && SEARCH_DIRS=("$DEFAULT_SEARCH_ROOT")

info()  { printf '  \033[32m[ok]\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m[skip]\033[0m %s\n' "$*"; }
dry()   { printf '  \033[36m[dry]\033[0m %s\n' "$*"; }

echo ""
echo "  Migrating legacy .ai-agents/ workspace folders to $VIBECRAFTED_HOME/artifacts/"
echo "  Searching: ${SEARCH_DIRS[*]}"
echo "  ─────────────────────────────────────────────────────────"
echo ""

# Wyciąga datę z nazwy pliku (format: 20260324_...) -> 2026_0324
# Jeśli nie ma daty w nazwie -> "legacy"
extract_date_prefix() {
  local fname="$1"
  local date_part
  date_part="$(echo "$fname" | grep -oE '^[0-9]{8}' || echo "")"
  if [[ -n "$date_part" ]]; then
    echo "${date_part:0:4}_${date_part:4:4}"
  else
    echo "legacy"
  fi
}

# Wyciąga datę z najnowszego pliku w katalogu (dla subdirów w pipeline/)
newest_date_in_dir() {
  local dir="$1"
  local dirname_base
  dirname_base="$(basename "$dir")"

  # Najpierw szukamy daty w plikach wewnątrz
  local newest_file
  # shellcheck disable=SC2012
  newest_file="$(ls -t "$dir" 2>/dev/null | head -1)" || true
  if [[ -n "$newest_file" ]]; then
    local file_date
    file_date="$(extract_date_prefix "$newest_file")"
    if [[ "$file_date" != "legacy" ]]; then
      echo "$file_date"
      return
    fi
  fi

  # Fallback: data z nazwy samego katalogu (np. 20260307_loct_dist_...)
  local dir_date
  dir_date="$(extract_date_prefix "$dirname_base")"
  echo "$dir_date"
}

# Przenosi pojedynczy plik do właściwego katalogu dat
move_file() {
  local file="$1"
  local target_base="$2"
  local folder="$3"

  local fname
  fname="$(basename "$file")"
  local ymd
  ymd="$(extract_date_prefix "$fname")"
  local dest="$target_base/$ymd/$folder"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    dry "mv $file -> $dest/$fname"
  else
    mkdir -p "$dest"
    mv "$file" "$dest/"
  fi
}

# Przenosi subdirectory (np. pipeline/<slug>/) według daty najnowszego pliku
move_subdir() {
  local subdir="$1"
  local target_base="$2"
  local folder="$3"

  local slug
  slug="$(basename "$subdir")"
  local ymd
  ymd="$(newest_date_in_dir "$subdir")"
  local dest="$target_base/$ymd/$folder/$slug"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    dry "mv $subdir/ -> $dest/"
  else
    mkdir -p "$dest"
    rsync -a --remove-source-files "$subdir/" "$dest/"
    find "$subdir" -depth -type d -empty -delete 2>/dev/null || true
  fi
}

find "${SEARCH_DIRS[@]}" -maxdepth 4 -type d -name ".ai-agents" 2>/dev/null | while read -r agents_dir; do
  repo_root="$(dirname "$agents_dir")"

  # Pobierz <org>/<repo> z git remote
  org_repo="$(cd "$repo_root" && git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/([^/.]+)(\.git)?$|\1/\2|' || true)"

  if [[ -z "$org_repo" ]]; then
    # Fallback jeśli repo nie ma origina – używamy nazwy katalogu
    org_repo="local/$(basename "$repo_root")"
  fi

  target_base="$VIBECRAFTED_HOME/artifacts/$org_repo"
  moved_something=false

  echo "  Repo: $org_repo"

  for folder in plans pipeline reports tmp; do
    src_dir="$agents_dir/$folder"

    # Skupiamy się TYLKO na rzeczywistych katalogach, omijamy puste i symlinki
    if [[ -d "$src_dir" && ! -L "$src_dir" ]]; then

      # Sprawdzamy czy katalog nie jest pusty
      if [ "$(ls -A "$src_dir" 2>/dev/null)" ]; then

        if [[ "$DRY_RUN" == "--dry-run" ]]; then
          # W trybie dry-run pokazujemy co by się stało
          for item in "$src_dir"/*; do
            [[ -e "$item" ]] || continue
            if [[ -d "$item" ]]; then
              move_subdir "$item" "$target_base" "$folder"
            else
              move_file "$item" "$target_base" "$folder"
            fi
          done
        else
          # Prawdziwa migracja: plik po pliku z routingiem po dacie
          for item in "$src_dir"/*; do
            [[ -e "$item" ]] || continue
            if [[ -d "$item" ]]; then
              move_subdir "$item" "$target_base" "$folder"
            else
              move_file "$item" "$target_base" "$folder"
            fi
          done

          # Usuwamy pustą strukturę po migracji
          find "$src_dir" -depth -type d -empty -delete 2>/dev/null || true

          # P1: Symlink wsteczny TYLKO dla reports/ — stare ścieżki nie złamią się
          if [[ "$folder" == "reports" && ! -e "$src_dir" ]]; then
            # Linkujemy do najnowszego katalogu dat w reports
            # (symlink do target_base/*/reports nie ma sensu, więc linkujemy do latest)
            latest_reports="$(find "$target_base" -type d -name "reports" | sort -r | head -1)" || true
            if [[ -n "$latest_reports" ]]; then
              ln -sf "$latest_reports" "$src_dir"
              info "symlink: $src_dir -> $latest_reports"
            fi
          fi

          info "$folder migrated (date-routed) -> $target_base/<date>/$folder/"
        fi
        moved_something=true
      else
        # Folder jest pusty, sam folder (bez plików) możemy po prostu zutylizować
        if [[ "$DRY_RUN" != "--dry-run" ]]; then
          rmdir "$src_dir" 2>/dev/null || true
        fi
      fi
    elif [[ -L "$src_dir" ]]; then
      # Posprzątanie śmieciowych symlinków po dawnych testach migracji
      warn "$folder stands as symlink, removing link."
      if [[ "$DRY_RUN" != "--dry-run" ]]; then
        rm "$src_dir" 2>/dev/null || true
      fi
    fi
  done

  if [ "$moved_something" = false ]; then
    warn "nothing to move in $org_repo"
  fi

done

echo ""
echo "  Przeprowadzka zakonczona."
if [[ "$DRY_RUN" == "--dry-run" ]]; then
  echo "  (Dzialal tryb symulacji: --dry-run. Aby dokonac przeniesin, uruchom skrypt bez --dry-run!)"
fi
echo ""

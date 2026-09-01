#!/usr/bin/env bash
# reelmine — full pipeline for one handle.
#
#   ./run.sh <handle> [--top N] [--bottom N]
#
# Safe to re-run. scrape resumes from disk, fetch and listen skip work that is
# already done. If Instagram throttles the scrape, run it again later and it
# picks up from the last saved page.
set -euo pipefail

HANDLE="${1:?usage: ./run.sh <handle> [--top N] [--bottom N]}"; shift || true
HANDLE="${HANDLE#@}"
TOP=15; BOTTOM=15
while [[ $# -gt 0 ]]; do
  case "$1" in
    --top)    TOP="$2";    shift 2 ;;
    --bottom) BOTTOM="$2"; shift 2 ;;
    *) echo "unknown flag: $1" >&2; exit 1 ;;
  esac
done

cd "$(dirname "$0")"
say() { printf '\n\033[1m== %s\033[0m\n' "$1" >&2; }

say "1/6 scrape @$HANDLE"
python3 bin/scrape.py "$HANDLE"

say "2/6 rank (top $TOP, bottom $BOTTOM)"
python3 bin/rank.py "$HANDLE" --top "$TOP" --bottom "$BOTTOM"

say "3/6 fetch media"
python3 bin/fetch.py "$HANDLE"

say "4/6 transcribe"
python3 bin/listen.py "$HANDLE"

say "5/6 build corpus"
python3 bin/corpus.py "$HANDLE"

say "6/6 mechanical deltas"
python3 bin/report.py "$HANDLE" > /dev/null

cat >&2 <<EOF

Done. Now hand these to your agent:

  data/$HANDLE/report.md     the countable deltas, measured first
  data/$HANDLE/corpus.md     the evidence
  prompts/extract.md         how to analyse it
  prompts/emit.md            how to turn the analysis into skills

EOF

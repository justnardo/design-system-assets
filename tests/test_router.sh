#!/usr/bin/env bash
# Smoke test for route_asset.py. Each line: prompt | expected_type | expected_route
#
# Routing/refuse cases legitimately exit non-zero (1=unintelligible, 2=refused),
# so we capture stdout regardless of exit code, then validate the JSON.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROUTER="$SCRIPT_DIR/../scripts/route_asset.py"

declare -a tests=(
  "hero photo for about page|photo|generate_asset.py"
  "hero photo for home page|photo|generate_asset.py"
  "Open Graph share card for pricing|og|generate_asset.py"
  "Twitter card for feature launch|og|generate_asset.py"
  "spot illustration for empty state|illustration|generate_asset.py"
  "decorative wave divider|decorative_svg|HAND_WRITE_SVG"
  "seamless texture pattern|pattern|generate_asset.py"
  "brand logo concept|logo_concept|generate_asset.py"
  "favicon|logo_concept|generate_asset.py"
  "menu icon|icon|fetch_icon.py"
  "menu|icon|fetch_icon.py"
  "hamburger|icon|fetch_icon.py"
  "user profile icon|icon|fetch_icon.py"
  "heart icon|icon|fetch_icon.py"
  "calendar|icon|fetch_icon.py"
  "bar chart of monthly revenue|chart|USE_CHARTING_LIBRARY"
  "pie chart of user engagement|chart|USE_CHARTING_LIBRARY"
  "data viz for the dashboard|chart|USE_CHARTING_LIBRARY"
  "photo of Mr. Johnson, our CEO|refuse_real_person|DO_NOT_GENERATE"
  "real product photo for our sauce bottle|refuse_real_product|DO_NOT_GENERATE"
  "something for the page|unknown|ESCALATE"
)

PASS=0
FAIL=0

for test in "${tests[@]}"; do
  IFS='|' read -r prompt expected_type expected_route <<< "$test"

  # Capture stdout once. Refuse cases exit 2; treat any exit code as
  # acceptable here — what matters is the JSON content on stdout.
  result=$(python "$ROUTER" --request "$prompt" 2>/dev/null) || true

  # Validate JSON and extract both fields in a single Python invocation.
  # If parsing fails, mark this case FAIL — don't silently fall through to
  # an empty-string comparison.
  if ! parsed=$(printf '%s' "$result" | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
except (json.JSONDecodeError, ValueError):
    sys.exit(2)
print(d.get("asset_type", ""))
print(d.get("route", ""))
'); then
    echo "FAIL: $prompt"
    echo "      router did not produce valid JSON"
    echo "      raw: ${result:0:200}"
    FAIL=$((FAIL + 1))
    continue
  fi

  actual_type=$(printf '%s' "$parsed" | sed -n '1p')
  actual_route=$(printf '%s' "$parsed" | sed -n '2p')

  if [ "$actual_type" = "$expected_type" ] && [ "$actual_route" = "$expected_route" ]; then
    echo "PASS: $prompt -> $actual_type"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $prompt"
    echo "      expected: $expected_type / $expected_route"
    echo "      got:      $actual_type / $actual_route"
    FAIL=$((FAIL + 1))
  fi
done

echo
echo "Results: $PASS passed, $FAIL failed"
exit "$FAIL"

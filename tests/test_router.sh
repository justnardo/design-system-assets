#!/bin/bash
# Smoke test for route_asset.py. Each line: prompt | expected_type | expected_route

set -e

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
  result=$(python scripts/route_asset.py --request "$prompt" 2>/dev/null)
  actual_type=$(echo "$result" | python -c "import json,sys; print(json.loads(sys.stdin.read())['asset_type'])")
  actual_route=$(echo "$result" | python -c "import json,sys; print(json.loads(sys.stdin.read())['route'])")

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
exit $FAIL

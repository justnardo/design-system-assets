# Review Rubric

The reviewer scores every generated raster asset on five dimensions, 0–10 each.

## The five dimensions

### 1. color_match (0–10)
Do the dominant colors in the image match the brand palette?

- **9–10:** Brand colors clearly visible and dominant. The palette feels intentional.
- **7–8:** Brand colors present but not dominant; image isn't fighting the palette.
- **5–6:** Some palette overlap but image leans on colors outside the brand.
- **3–4:** Image uses a palette that conflicts with brand (e.g. cool tones for a warm brand).
- **0–2:** Wrong palette entirely.

### 2. style_consistency (0–10)
Does the image match the visual register the brand has established?

For a brand whose `tokens.style_directives.include` says "editorial, warm, soft shadow, natural light", a glossy 3D render scores low even if the colors are right.

- **9–10:** Could appear in a magazine spread for this brand.
- **7–8:** Right register, minor inconsistencies.
- **5–6:** Adjacent register; not wrong but not fully on-brand.
- **3–4:** Different register from the brand (e.g. flat illustration for an editorial brand).
- **0–2:** Wholly wrong register.

### 3. subject_correctness (0–10)
Does the image actually depict what was requested?

- **9–10:** Subject matches intent precisely.
- **7–8:** Subject matches with minor interpretive variance.
- **5–6:** Subject is in the right ballpark but key details are wrong (wrong setting, wrong age range, wrong activity).
- **3–4:** Subject is loosely related to the request.
- **0–2:** Subject is wrong. Hard fail.

### 4. technical_quality (0–10)
Is the image free of obvious AI artifacts?

Look for: extra fingers, warped text, melted faces, broken anatomy, blurred or doubled subjects, noise patterns where there should be smooth gradients, uncanny-valley expressions, inconsistent lighting between elements.

- **9–10:** Indistinguishable from professional work at typical viewing size.
- **7–8:** Minor artifacts only visible on close inspection.
- **5–6:** Visible artifacts that would be noticed by an attentive viewer.
- **3–4:** Obvious artifacts visible at a glance.
- **0–2:** Broken render. Hard fail.

### 5. brand_fit (0–10)
The holistic question: would the brand's designer approve this for the project?

This is intentionally subjective — it's the reviewer's senior-designer judgment. It catches things that score okay on individual dimensions but feel wrong overall (a technically fine image that's just generic, or one that hits the palette but feels off-brand for some other reason).

## Verdict logic

```
if hard_fail_reason:                   -> escalate_to_human
elif any score < 5:                    -> regenerate
elif avg >= 8 AND all scores >= 7:     -> approved
elif avg >= 6.5:                       -> regenerate
else:                                  -> escalate_to_human
```

## Why "approved" is intentionally hard to hit

The skill exists to prevent generic-looking output from shipping. Setting the bar at "all five scores at 7+ AND average at 8+" means borderline assets get a second pass with feedback rather than slipping through.

If you find approval rate is too low for your use case (e.g. you're prototyping and don't need every asset to be brand-perfect), you can run with `--json` and apply your own threshold logic in a calling script.

## What "regenerate" feedback should look like

The reviewer's `regenerate_advice` should be specific and prompt-actionable, not vague. Examples of good vs. bad advice:

**Bad:** "Make it more on-brand."
**Good:** "Shift the dominant lighting from cool blue to warm gold to match the brand's natural-light directive."

**Bad:** "The composition isn't right."
**Good:** "Recompose with the subject on the left third and negative space on the right; current composition centers the subject and crowds the frame."

**Bad:** "Looks generic."
**Good:** "Replace the staged studio framing with a candid documentary-style angle; add specific environmental details (e.g. a window, a table with brand-relevant objects)."

When regeneration advice from the reviewer is too vague, the calling skill should ask the user to refine the original intent instead of blind-regenerating.

## Hard fails

A hard fail (`hard_fail_reason` set) means the asset is fundamentally unusable, not just imperfect. Examples:
- Subject is wrong (was supposed to be elderly woman gardening; image shows a young man at a desk)
- Image contains text in the wrong language
- Image contains offensive or inappropriate content
- Image is broken (incomplete render, extreme distortion)

Hard fails ALWAYS escalate to human — the skill doesn't try to auto-fix them, because the failure mode is at the level of intent, not execution.

# Prompt Engineering

The core value of this skill is the design-system-to-prompt translation. This document explains how `generate_asset.py` builds the style prefix and how to override it when the default isn't getting the result you want.

## How the default style prefix is built

For every asset, `build_style_prefix()` produces a directive prompt in this order:

1. **Visual register** — "Photographic image", "Editorial illustration", "Seamless decorative pattern", etc. Sets what kind of output to produce.
2. **Tone & industry** — Pulled from `tokens.tone` and `tokens.industry`. Sets the emotional register.
3. **Color palette** — Named with hex codes. "Color palette must include: primary #805158, secondary #4f634f, background #fbfaee."
4. **Typography hint** — Only injected for assets where text appears (OG cards, logo concepts).
5. **Include directives** — From `tokens.style_directives.include`. The qualities the brand DOES want.
6. **Exclude directives** — From `tokens.style_directives.exclude`. The qualities the brand NEVER wants. Critical for fighting the generic AI look.
7. **Subject** — The user's specific prompt for THIS asset, appended at the end.

## Why this order matters

Image models pay disproportionate attention to the FRONT of the prompt. Putting the brand directives first means they shape the entire generation. Putting "Subject:" last means the model has already locked in the brand context before it considers what to draw.

Putting the AVOID directives in capitals and as a separate clause is deliberate — it gives the model a clear negative space. "AVOID: glassmorphism; gradient buttons; parallax effects" gets through more reliably than burying it in prose.

## When the default isn't enough

If you're getting output that's technically on-brand but visually flat, try these adjustments:

### Make the subject more cinematic
Default prompts often say "a person doing X." Cinematic prompts work better: "Wide-angle photograph of [person] [action], [time of day], [lighting quality], shot on [film stock or camera reference]." Example: "Wide-angle photograph of an elderly woman tending herbs, late afternoon, golden hour light, shot on Portra 400 film."

### Use a style anchor for multi-asset projects
Generate one "style anchor" first. This becomes the visual law for the rest:

```bash
python generate_asset.py --anchor \
  --tokens design_tokens.json \
  --prompt "establishing brand mood: a quiet morning in a residential garden, warm tones" \
  --output .asset-cache/style_anchor.png
```

The anchor's prompt should describe a key visual that captures the brand mood. Subsequent prompts will be more consistent because the model has a reference for the visual world.

### Inject specific photography directives
For photography especially, generic prompts produce generic photos. Add specific qualities:

- "Natural window light from camera left"
- "Shallow depth of field, f/2.8"
- "Editorial composition with negative space on the right for text overlay"
- "Skin tones rendered warmly"
- "Color grading: muted shadows, soft highlights"

### Override the prefix entirely (advanced)
For cases where the default prefix conflicts with what you need (e.g. a moody campaign image for a normally bright brand), pass `--override-prefix "<your prefix>"` and `generate_asset.py` will use yours instead. *(Note: this flag is reserved for v2; for v1 you'd edit the prompt manually.)*

## Common failure patterns

**Output looks "AI-generated" despite a strong design system.** The brand directives are getting drowned out by an under-specified subject. Make the subject prompt more visually concrete — composition, lighting, camera or rendering style.

**All my assets look slightly different from each other.** Style drift. Use the style anchor pattern. If you're already using it, your subject prompts are too varied — find a common compositional thread (always shot at the same time of day, always at the same camera angle, always the same level of zoom).

**Colors don't match the palette.** The model is interpreting "primary #805158" loosely. Try naming the color descriptively: "warm dusty rose tones" alongside the hex. Image models often respond better to color descriptions than hex codes alone.

**Subjects feel staged or stocky.** Add "natural, candid moment" and "documentary-style framing" to the prompt. Avoid words like "professional" and "premium" — they push toward stock photo aesthetics.

## Manual prompt construction

If you want to see exactly what prompt would be sent without running the API call:

```bash
python generate_asset.py --type photo --tokens design_tokens.json \
  --prompt "<your subject>" --output /tmp/test.png --dry-run
```

This prints the final prompt and exits. Useful for iterating on prompt wording before committing to an API spend.

# BYOK Setup

This skill is bring-your-own-keys. The user supplies API credentials for the providers they want to use.

## Required keys (depending on usage)

| Key | What it's for | Required? |
|-----|---------------|-----------|
| `OPENAI_API_KEY` | gpt-image-1 image generation | Yes if using OpenAI provider (default) |
| `GEMINI_API_KEY` | Gemini image generation | Optional — alternative provider |
| `ANTHROPIC_API_KEY` | Asset review (Claude vision) | Yes for the review step |

## Setting keys for a Claude Code session

The simplest setup — exports in your shell:

```bash
export OPENAI_API_KEY=sk-proj-...
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=AIza...   # optional
```

These persist for the current shell. Add to `~/.zshrc` or `~/.bashrc` to persist across sessions.

## Project-level config (recommended for agency work)

When you're juggling multiple client projects with different keys (or different budgets per client), use a `.env` file at the project root:

```bash
# .env (do NOT commit this)
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
```

Source it at the start of each session:

```bash
source .env
# or
export $(grep -v '^#' .env | xargs)
```

Add `.env` to `.gitignore` immediately:

```
echo ".env" >> .gitignore
```

A starter `.env.example` ships with the skill — copy it to `.env` and fill in your values.

## Where to get keys

- **OpenAI:** platform.openai.com → API keys. Note that image generation may require organization verification — enable in account settings if first calls error on auth.
- **Anthropic:** console.anthropic.com → API keys.
- **Gemini:** aistudio.google.com → Get API key. Free tier generous for most testing.

## Key safety

- Never commit keys to a git repo. The skill writes API responses to `.asset-cache/` and metadata sidecars, but not the keys themselves.
- For agency client work, generate per-client OpenAI sub-keys (Project Keys in OpenAI's console) so you can revoke one client's access without touching others.
- If a key leaks, rotate it from the provider's console — don't try to track down where it leaked first.

## Troubleshooting

**"OPENAI_API_KEY not set" but I exported it.** The export is shell-scoped. If you opened a new terminal, you need to re-export. Check with `echo $OPENAI_API_KEY` (should show your key, not empty).

**OpenAI returns 401 or "organization verification required."** Image generation endpoints require your OpenAI organization to be verified. Go to platform.openai.com → Settings → Organization → verify. Takes about 10 minutes once submitted.

**OpenAI returns "billing_hard_limit_reached" or 429.** You've hit your spending cap. Either raise the cap or wait for the reset window.

**Gemini returns 403 with "API_KEY_INVALID."** Gemini keys are tied to a specific Google Cloud project. If you regenerated the key, the old one is dead — update your env var.

**Anthropic returns 401.** API key is invalid or expired. Generate a fresh one at console.anthropic.com.

**"All my API calls are slow."** Image generation is genuinely slow (10–30s per image). If you're generating a full site's worth, expect a few minutes. You can parallelize multiple `generate_asset.py` calls in a shell loop — the cache prevents duplicate work.

## Cost ceilings (recommended)

For agency work, set a hard spending cap on the OpenAI key BEFORE running this skill on a new client project. A normal project run should not exceed $5 in API spend; if you hit $20+, something is wrong (probably regeneration loops on a hard-failing asset).

For OpenAI: platform.openai.com → Billing → Limits → "Set monthly budget."

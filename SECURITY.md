# Security Guidelines

## Sensitive Data Protection

This project handles API keys and personal information. Please follow these guidelines:

### Never Commit Secrets
The following files are **never** committed to GitHub (protected by `.gitignore`):

- **`.env`** — Contains your actual API keys and Discord tokens
  - Copy `.env.example` and fill in your real credentials locally
  - Never push your `.env` file to GitHub

- **`data/master_resume.yaml`** — Contains your personal/confidential resume
  - Copy `data/master_resume.example.yaml` and customize with your information
  - Never push your actual resume to GitHub

### API Key Rotation

If you ever accidentally commit a secret to GitHub:

1. **Immediately revoke the key** in the respective service:
   - OpenAI: https://platform.openai.com/api-keys
   - Discord: https://discord.com/developers/applications → Regenerate Token
   - Anthropic: https://console.anthropic.com/account/keys

2. **Remove from Git history**:
   ```bash
   # Option 1: Remove from recent commits (if not pushed)
   git reset --soft HEAD~1  # Undo last commit
   rm .env
   git commit -m "Remove secrets"

   # Option 2: Full history removal (if already pushed)
   pip install git-filter-repo
   git filter-repo --invert-paths --path .env
   git push --force-with-lease
   ```

### Code Review Checklist

Before pushing any code, verify:

- [ ] No hardcoded API keys (grep for `sk-`, `gpt-`, `MTQ` patterns)
- [ ] No Discord webhooks or bot tokens in source
- [ ] No personal information (names, emails, phone numbers, addresses)
- [ ] No test credentials left in code
- [ ] `.env` file is in `.gitignore`
- [ ] `data/master_resume.yaml` is in `.gitignore`
- [ ] Example files (`.example` or `.example.yaml`) have placeholder values only

### Running Tests Safely

Test files can access real API keys through environment variables (loaded from `.env`):

```bash
# Run e2e tests (uses your OpenAI API key from .env)
python test_e2e_approval.py

# Run unit tests (no external API calls)
uv run pytest tests/ -v
```

All test data is sanitized and uses placeholder values except where `.env` variables are explicitly referenced.

### Discord Bot Token Security

- **Never share your bot token** — it grants full bot permissions
- If token is exposed, regenerate immediately in [Discord Developer Portal](https://discord.com/developers/applications)
- The bot token is only needed in `.env` for the listening functionality
- The webhook URL is less sensitive (send-only, revokable per-message)

### Deployment Security

When deploying to a VPS:

1. Never commit `.env` to the server repo
2. Create `.env` directly on the server (not from Git)
3. Use restricted file permissions: `chmod 600 .env`
4. Store secrets in environment variables or `.env` only, never in systemd service files
5. Review service file permissions: `sudo ls -la /etc/systemd/system/job-hunter.service`

### Reporting Security Issues

If you discover a security vulnerability in this project:

1. **Do NOT open a public issue**
2. Email security details to the maintainer
3. Include: vulnerability description, steps to reproduce, potential impact
4. Allow time for a patch before public disclosure (30-90 days)

### Credential Examples (Safe)

These are SAFE to include in docs/code because they are clearly placeholders:

```
OPENAI_API_KEY=sk-proj-...
DISCORD_BOT_TOKEN=...
sk-ant-...
https://discord.com/api/webhooks/...
```

These contain placeholder dots (`...`) or example format only — not real credentials.

---

**Last Updated**: 2026-04-02

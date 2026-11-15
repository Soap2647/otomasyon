# otomasyon — personal ops bot

The scripts that run my day: a Telegram assistant that knows my calendar, courses and inbox, plus a nightly routine that backs up, pushes unsaved work, updates the machine and shuts it down safely.

Built for one person (me), on Windows, with Python 3.12 and `uv`. Everything is read-only towards the outside world: it never sends mail, never writes to Google Calendar and never does anything irreversible without a cancellable warning.

## What it does

**Telegram assistant (`bot.py`, `asistan.py`)**
- Morning briefing: today's courses, calendar events, weather, unread mail summary and headlines.
- 22:30 "tomorrow" message and reminders 15 minutes before timed events. At most 3 loud notifications a day, the rest are silent.
- Free-text chat: "cuma 14:00 dişçi" becomes an event, "vize 20 Kasım" becomes a deadline. The LLM answers in a fixed JSON schema, so the bot only adds, completes or edits its own items.
- Every bot message is also appended to the Obsidian daily note.
- Answers only the owner's chat id.

**Nightly runner (`gece.py`)**, dry run by default, `--uygula` to act:
1. `yedek`: rclone backup to Google Drive, with dated copies of changed files and a Sunday second copy.
2. `gitwip`: pushes uncommitted work in every repo to a `wip/auto` branch without touching the working tree, index or current branch.
3. `bakim`: winget upgrades (pinned packages skipped) and disk health.
4. `kapanis`: shuts down only if the user is idle, no fullscreen app is open and it is before the cut-off time, after a 5-minute cancellable warning.

**Data sources:** courses and exams from `ders.toml`, Google Calendar through the secret iCal URL, Turkish public holidays, Gmail over read-only IMAP (OTP codes and links are masked), RSS feeds and Open-Meteo.

**Models:** Claude through the `claude -p` CLI for everything. Free fallback models (Gemini, OpenRouter, NVIDIA) are used only for public data such as headlines, never for mail content.

## Setup

```powershell
uv sync
copy config.example.toml config.toml   # then edit
copy ders.example.toml ders.toml       # your timetable
copy .env.example .env                 # tokens and app passwords
uv run python -m otomasyon.secrets     # shows which secrets are set (never their values)

uv run python -m otomasyon.bot         # Telegram bot
uv run python -m otomasyon.gece        # nightly run, dry run
```

`kurulum/` has PowerShell scripts that register the bot and the nightly runner as Windows scheduled tasks.

## License

MIT, see [LICENSE](LICENSE).

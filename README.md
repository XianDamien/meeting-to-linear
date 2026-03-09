# Meeting-to-Linear

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that automates the end-to-end workflow of processing meeting recordings into structured Linear issues, documents, and email notifications.

## What It Does

```
Meeting Video → ASR Transcription → Summary → Linear Issues → Linear Document → Email Notification → WeChat Message
```

- **Video Processing**: Transcribe meeting videos locally via Qwen ASR (optional: upload to OSS for video playback links)
- **Meeting Summary**: Generate structured meeting summaries with key decisions and action items
- **Linear Issues**: Batch-create Linear issues with proper priority, labels, assignees, and parent-child relationships
- **Linear Documents**: Create meeting minutes as Linear documents linked to a project
- **Email Notifications**: Send HTML-formatted meeting recap emails with Linear-style issue cards
- **WeChat Notification**: Generate copy-paste-ready WeChat messages with short URLs

## Installation

### As a Claude Code Skill (Recommended)

```bash
# Clone to your Claude Code skills directory
git clone https://github.com/damien-cli/meeting-to-linear.git ~/.claude/skills/meeting-to-linear

# Install Python dependencies
cd ~/.claude/skills/meeting-to-linear
pip install -r requirements.txt

# Install transcription dependencies
cd oss-config
uv sync

# (Optional) Install OSS upload support
uv sync --extra oss
```

### Manual Setup

```bash
git clone https://github.com/damien-cli/meeting-to-linear.git
cd meeting-to-linear
pip install -r requirements.txt
```

## Quick Start

### 1. Configure

```bash
# Create your config from the example
cp config.example.json config.json
# Edit config.json with your actual values
```

Set up your Linear API key:

```bash
mkdir -p ~/.linear
echo 'lin_api_YOUR_KEY_HERE' > ~/.linear/config
```

Get your API key from [Linear Settings > Security](https://linear.app/settings/account/security).

### 2. Use with Claude Code

Once installed as a skill, Claude Code will automatically use it when you say things like:

- "Process the meeting recording at /path/to/video.mp4"
- "Create Linear issues from this meeting transcript"
- "Upload to Linear"

### 3. Use Standalone

```bash
# Create issues from a JSON input
python3 scripts/create_linear_issues.py \
  --issues "issues-input.json" \
  --output "issues.json"

# Create a Linear document
python3 scripts/create_linear_issues.py \
  --document-only \
  --document-title "Meeting Minutes" \
  --document-content "summary.md"

# Send email notification
python3 scripts/send_linear_notification.py \
  --issues-json "issues.json" \
  --date "2025-01-19" \
  --topic "Sprint Review" \
  --summary "summary.md"
```

## Directory Structure

```
meeting-to-linear/
├── SKILL.md                    # Claude Code skill definition
├── config.example.json         # Example configuration (copy to config.json)
├── config_loader.py            # Unified config loader
├── requirements.txt            # Python dependencies
├── scripts/
│   ├── create_linear_issues.py # Create issues & documents via GraphQL
│   ├── linear_graphql.py       # Linear GraphQL API client
│   ├── list_issues.py          # List & report existing issues
│   ├── list_issues_simple.py   # Simple chronological issue list
│   ├── list_issues_todo.py     # Find issues needing attention
│   ├── cleanup_issues.py       # Issue cleanup utilities
│   ├── send_email.py           # SMTP email sender
│   └── send_linear_notification.py  # Meeting notification emails
├── references/
│   ├── api-config.md           # Linear API setup guide
│   ├── api-usage.md            # GraphQL API reference
│   ├── templates.md            # Templates for summaries, issues, emails
│   ├── label-ids.md            # Label UUID reference
│   ├── parent-child-issues.md  # Parent-child issue rules
│   ├── user-mapping.md         # Team member mapping reference
│   └── known-issues.md         # Troubleshooting guide
├── oss-config/                 # Video transcription & optional OSS upload
│   ├── process_meeting_video.py
│   ├── qwen_asr.py             # Qwen ASR transcription engine
│   ├── upload_to_oss.py
│   ├── .env.example
│   └── pyproject.toml
└── reports/                    # Generated reports (gitignored)
```

## Configuration

All personal settings live in `config.json` (gitignored). See [`config.example.json`](config.example.json) for the full schema:

| Section | Purpose |
|---------|---------|
| `linear` | Team name, project name, API key path |
| `email` | SMTP server, sender, auth code |
| `team_members` | Linear username → real name + email mapping |
| `default_recipients` | Email notification recipients |
| `oss` | Aliyun OSS credentials (optional, for video upload) |
| `asr` | Qwen/DashScope API key (for transcription) |

For the video processing pipeline (`oss-config/`), create `oss-config/.env` from `oss-config/.env.example`. Only `DASHSCOPE_API_KEY` is required; OSS credentials are optional (needed only with `--use-oss`).

## Dependencies

- **Python 3.10+**
- **requests** - HTTP client for Linear GraphQL API
- **Network proxy** recommended for Linear API access in China (`export ALL_PROXY=socks5://127.0.0.1:7890`)

Optional (for video processing):
- **dashscope** - Qwen ASR API client
- **librosa**, **soundfile**, **silero-vad** - Audio processing and VAD segmentation
- [**uv**](https://docs.astral.sh/uv/) - Recommended Python package manager

Optional (for OSS upload):
- **oss2** - Aliyun OSS SDK (`uv sync --extra oss`)

## License

[MIT](LICENSE)

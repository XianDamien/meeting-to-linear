# Meeting-to-Linear

> 一句话说完会议，剩下的交给 AI。

会议录了半小时视频？丢给它——3 分钟出转录，再自动整理成 Linear Issues、会议纪要文档、邮件通知，全流程无需手动操作。

```
会议视频 → 语音转录 → 结构化摘要 → Linear Issues → 会议纪要文档 → 邮件通知 → 微信消息
         ↑ 3 min/50min       ↑ AI 生成            ↑ GraphQL 批量创建
```

## 谁需要这个

- 每周开完会还要花半天整理会议纪要和 TODO 的团队
- 用 Linear 管理项目但讨厌手动录 issue 的开发者
- 想让 Claude Code 帮你把「嘴上说的」变成「系统里跟踪的」

## 功能一览

| 能力 | 说明 |
|------|------|
| 视频转录 | 本地 Qwen ASR，50 分钟视频 ~3 分钟完成，支持中英混合 |
| 会议摘要 | 自动提取核心议题、技术决策、行动项 |
| Linear Issues | 批量创建，自动匹配优先级、标签、负责人、父子关系 |
| Linear 文档 | 会议纪要直接关联到项目文档 |
| 邮件通知 | HTML 格式 issue 卡片，支持附件 |
| 微信消息 | 生成可直接复制粘贴的通知文本 |

## 快速开始

### 1. 下载

```bash
git clone https://github.com/XianDamien/meeting-to-linear.git
cd meeting-to-linear
```

### 2. 安装依赖

```bash
# 基础依赖（Linear API + 邮件）
pip install -r requirements.txt

# 视频转录依赖
cd oss-config
uv sync
```

> 没有 `uv`？安装：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 3. 配置

**必需：Linear API Key**

```bash
mkdir -p ~/.linear
echo 'lin_api_YOUR_KEY_HERE' > ~/.linear/config
```

获取地址：[Linear Settings > API](https://linear.app/settings/account/security)

**必需：Qwen ASR API Key（转录用）**

```bash
cd oss-config
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

获取地址：[阿里云 DashScope](https://dashscope.console.aliyun.com/apiKey)

**必需：项目配置**

```bash
cp config.example.json config.json
# 编辑 config.json，填入团队信息、邮箱、成员映射
```

**可选：OSS 上传**（需要视频回看链接时）

```bash
cd oss-config
uv sync --extra oss
# 在 .env 中补充 OSS_ACCESS_KEY_ID 等凭证
```

### 4. 开跑

**作为 Claude Code Skill 使用（推荐）**

```bash
# 放到 skills 目录
git clone https://github.com/XianDamien/meeting-to-linear.git ~/.claude/skills/meeting-to-linear
```

然后对 Claude Code 说：

- "处理这个会议录像 /path/to/video.mp4"
- "上传到 Linear"
- "Create Linear issues from this meeting"

Claude 会自动走完全流程。

**独立使用**

```bash
# 转录视频
cd oss-config
uv run process_meeting_video.py "/path/to/video.mp4" --output "/path/to/output"

# 创建 Linear Issues
python3 scripts/create_linear_issues.py \
  --issues "issues-input.json" --output "issues.json"

# 创建会议纪要文档
python3 scripts/create_linear_issues.py \
  --document-only \
  --document-title "2026年03月09日_会议纪要" \
  --document-content "summary.md"

# 发送邮件通知
python3 scripts/send_linear_notification.py \
  --issues-json "issues.json" \
  --date "2026-03-09" --topic "Sprint Review" \
  --summary "summary.md"
```

## 项目结构

```
meeting-to-linear/
├── README.md
├── SKILL.md                         # Claude Code skill 定义
├── config.example.json              # 配置模板（复制为 config.json）
├── config_loader.py                 # 统一配置加载
├── requirements.txt                 # 基础依赖
├── scripts/
│   ├── create_linear_issues.py      # 创建 issues & 文档（GraphQL）
│   ├── linear_graphql.py            # Linear API 客户端
│   ├── send_email.py                # SMTP 邮件发送
│   ├── send_linear_notification.py  # 会议通知邮件
│   ├── list_issues.py               # 列出现有 issues
│   └── cleanup_issues.py            # Issue 清理工具
├── oss-config/                      # 视频转录模块
│   ├── process_meeting_video.py     # 入口：视频 → 转录文件
│   ├── qwen_asr.py                  # Qwen ASR 转录引擎
│   ├── upload_to_oss.py             # OSS 上传（可选）
│   ├── .env.example                 # 环境变量模板
│   └── pyproject.toml               # Python 依赖
└── references/                      # 参考文档
    ├── templates.md                 # 摘要/issue/邮件模板
    ├── api-usage.md                 # GraphQL API 参考
    ├── user-mapping.md              # 成员映射
    └── known-issues.md              # 常见问题
```

## 配置说明

所有个人配置在 `config.json`（已 gitignore），结构见 [`config.example.json`](config.example.json)：

| 配置项 | 用途 | 必需 |
|--------|------|------|
| `linear` | 团队名、项目名、API Key 路径 | Yes |
| `email` | SMTP 服务器、发件人、授权码 | Yes |
| `team_members` | Linear 用户名 → 姓名 + 邮箱 | Yes |
| `default_recipients` | 邮件通知收件人列表 | Yes |
| `asr` | DashScope API Key | Yes |
| `oss` | 阿里云 OSS 凭证 | No（仅 `--use-oss` 模式） |

## 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（视频转录模块的包管理）
- 中国大陆访问 Linear API 需代理：`export ALL_PROXY=socks5://127.0.0.1:7890`

## License

[MIT](LICENSE)

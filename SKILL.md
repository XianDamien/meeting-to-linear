---
name: meeting-to-linear
description: 将会议记录转换为 Linear issues 并发送邮件通知。当用户需要处理会议转录、创建 Linear issues 或发送会议邮件时使用。触发词："上传到linear"、"处理会议记录"、"create linear issues"。
---

# Meeting To Linear

将会议转录自动化处理为结构化文档和 Linear issues。

## 前置配置

- **依赖**: `cd ~/.claude/skills/meeting-to-linear && uv pip install -r requirements.txt`
- **API Key**: `mkdir -p ~/.linear && echo 'lin_api_xxx' > ~/.linear/config`（[获取密钥](https://linear.app/settings/account/security)，详见 `references/api-config.md`）
- **代理**: `export ALL_PROXY=socks5://127.0.0.1:7890`（推荐 SOCKS5，HTTP 代理可能遇到 SSL 错误）

## 工作流程

各步骤的模板和格式见 `references/templates.md`，API 用法见 `references/api-usage.md`。

```
会议视频 → 转录 → 生成摘要 → 生成 issues → 创建 Linear Issues → 创建文档 → 发送邮件 → 微信通知
```

### Step 1: 处理会议视频

默认：直接转录本地文件（只需 `DASHSCOPE_API_KEY`）：
```bash
cd ~/.claude/skills/meeting-to-linear/oss-config
uv run process_meeting_video.py "/path/to/video.mp4" --output "/path/to/YYYYMMDD"
```

可选：上传 OSS 后转录（适用于需要视频回看链接的场景）：
```bash
uv run process_meeting_video.py "/path/to/video.mp4" --output "/path/to/YYYYMMDD" --use-oss
```

输出到 `YYYYMMDD/` 目录：转录 `.txt`、字幕 `.srt`、时间戳 `.json`。OSS 模式额外输出 `video-url.txt`。转录文本重命名为 `YYYYMMDD.txt`。

### Step 2: 生成摘要文档

创建 `YYYYMMDD-summary.md`，包含：会议信息（日期用"YYYY年MM月DD日"格式）、参与人、主题、视频链接、核心议题、技术决策、下一步行动。视频 URL 从 `video-url.txt` 读取。

### Step 3: 生成 Issues

直接生成 `YYYYMMDD-issues-input.json`（跳过 issues.md），每个 issue 含 title/description/priority/status/assignee/labels。

### Step 4: 创建 Linear Issues

```bash
python3 scripts/create_linear_issues.py \
  --issues "issues-input.json" --output "issues.json"
```

创建子 issues 加 `--parent "LAN-XXX"`。脚本自动查找团队/项目/用户/标签 ID。查询现有 issues 用 `get_issue("LAN-XXX")` 和 `get_issues(team_key="LAN")`。

### Step 5: 创建 Linear 文档

```bash
python3 scripts/create_linear_issues.py \
  --issues "issues-input.json" --document-only \
  --document-title "YYYY年MM月DD日_会议纪要" \
  --document-content "summary.md"
```

### Step 6-7: 邮件通知

准备 `YYYYMMDD-issues.json`，展示邮件预览给用户确认后发送。

### Step 8: 微信通知

生成 `YYYYMMDD-wechat-notification.txt`。

---

## 关键规则

1. **先本地确认再上传**：本地文件是唯一真实来源，用户确认后才创建 Linear issues（ID 不可回收）
2. **创建前检查重复**：用 `get_issues()` 查最近 20 个，重合的更新而非新建
3. **邮件发送前必须用户确认**：展示收件人、主题、issues 列表
4. **固定收件人**：无论内容涉及谁，4 人全发（见 `references/user-mapping.md`）
5. **子任务不进邮件/微信**：只包含父 issues 和独立 issues
6. **微信用短 slug URL**：避免横杠断链（`https://linear.app/your-workspace/document/{slugId}`）
7. **隐私保护**：issue 内容用用户名，不用真实姓名
8. **创建后整合**：检查是否有可设置父子关系的 issues

## 错误处理

| 问题 | 解决方案 |
|------|----------|
| 标签未找到 | 脚本已修复（先搜 workspace 再搜 team）。UUID 见 `references/label-ids.md` |
| API Key 无效 | 检查 `~/.linear/config`，参考 `references/api-config.md` |
| 邮件数据错误 | 必须提供 `--issues-json`，否则脚本用硬编码示例数据 |
| GraphQL 报 deprecated | 用 `issues(filter:...)` 替代已废弃的 `issueSearch` |
| 其他问题 | 见 `references/known-issues.md` |

## 参考文件

| 文件 | 内容 |
|------|------|
| `references/templates.md` | 摘要/issue/邮件/微信模板和格式 |
| `references/api-usage.md` | GraphQL API 方法、JSON 格式、脚本参数 |
| `references/user-mapping.md` | 团队成员表和固定收件人列表 |
| `references/label-ids.md` | Workspace 标签 UUID |
| `references/parent-child-issues.md` | 父子 issue 整合规则 |
| `references/known-issues.md` | 脚本已知问题和解决方案 |

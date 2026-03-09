# 模板与格式参考

## Step 1: 分步执行（可选）

如需分别上传和转录（不用一键脚本时）：

1. 仅上传到 OSS:
```bash
cd ~/.claude/skills/meeting-to-linear/oss-config
uv run upload_to_oss.py /path/to/video.mp4 --output /path/to/url.txt
```

2. 使用 URL 转录:
```bash
cd ~/.claude/skills/qwen-asr-transcriber/scripts
uv run qwen_asr.py --model filetrans --url "https://your-bucket.oss-cn-shanghai.aliyuncs.com/meetings/YYYYMMDD/video.mp4" --output /path/to/output --srt
```

## Step 2: 摘要文档模板

```markdown
## 会议信息
- 日期: YYYY年MM月DD日
- 参与人: xxx, xxx
- 主题: xxx
- 视频回看: [点击观看](视频URL)

## 核心议题
### 1. 议题名称
- 要点

## 技术决策
## 当前进度
## 下一步行动
```

视频 URL 从 `YYYYMMDD/video-url.txt` 读取。

## Step 3: Issue 类别与模板

| 类别 | 标签 | 说明 |
|------|------|------|
| Feature | 🚀 | 新功能 |
| Improvement | ✨ | 功能改进 |
| Bug | 🐛 | 缺陷修复 |
| Tech Debt | 🔧 | 技术债务 |
| Security | 🔒 | 安全问题 |

**Issue 模板：**
```markdown
### [类别] Issue 标题

**优先级**: P0/P1/P2/P3
**状态**: Todo/Backlog/In Progress
**类型标签**: Feature/Improvement/Bug/Tech Debt
**负责人**: Linear用户名
**业务背景**: 背景说明
**解决方案**: 具体步骤
```

**优先级映射**：P0→1(Urgent), P1→2(High), P2→3(Medium), P3→4(Low)

## Step 6: 邮件 Issues JSON 格式

```json
[
  {
    "identifier": "LAN-XXX",
    "title": "Issue 标题",
    "priority": {"value": 2, "name": "High"},
    "assignee": "用户名",
    "labels": ["Feature"],
    "url": "https://linear.app/...",
    "status": "Todo"
  }
]
```

所有字段必填。邮件模板当前显示优先级徽章、类型徽章、负责人（状态徽章暂不显示）。

## Step 7: 邮件发送命令

```bash
python3 scripts/send_linear_notification.py \
  --issues-json "/path/to/YYYYMMDD-issues.json" \
  --date "YYYY-MM-DD" \
  --topic "会议主题" \
  --summary "/path/to/summary.md" \
  --transcript "/path/to/transcript.txt" \
  --video-url "$(cat /path/to/YYYYMMDD/video-url.txt)" \
  --to "recipient@example.com"
```

邮件特性：Linear 风格 HTML、负责人显示为 `真实姓名 (用户名)`、转录作为附件、自动保存到已发送。

## Step 8: 微信通知模板

```
本次 YYYY年MM月DD日 会议总结已保存在 Linear：
https://linear.app/your-team/document/{短slug}

创建了以下 issues：

• LAN-XXX: Issue标题 [类型] (优先级, 状态, 负责人)
https://linear.app/your-team/issue/TEAM-XXX
（包含子任务：LAN-YYY、LAN-ZZZ）
```

保存为 `YYYYMMDD-wechat-notification.txt`。

## 微信链接问题

Linear URL 包含标题中的横杠，微信会在横杠处断链。

**解决**：使用短 slug URL（只含 slug ID）：
- ✅ `https://linear.app/your-workspace/document/17a730aad007`
- ❌ `https://linear.app/your-workspace/document/2026年01月31日-会议纪要-17a730aad007`

从 API 返回的 `url` 字段提取末尾 slug ID 构建短 URL。

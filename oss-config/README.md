# 会议视频转录

## 快速开始（本地转录）

只需一个 API Key 即可转录会议视频，无需 OSS 配置。

### 1. 配置 API Key

```bash
cd ~/.claude/skills/meeting-to-linear/oss-config
cp .env.example .env
```

编辑 `.env`，填入 Qwen API Key：
```bash
DASHSCOPE_API_KEY=你的DashscopeKey
```

获取 API Key: https://dashscope.console.aliyun.com/apiKey

### 2. 安装依赖

```bash
uv sync
```

### 3. 转录

```bash
uv run process_meeting_video.py /path/to/video.mp4 --output /path/to/output
```

输出 `.txt`（全文）、`.srt`（字幕）、`.json`（时间戳）到指定目录。

---

## 高级模式：OSS 上传 + 转录

适用于需要视频回看链接的场景。上传到 OSS 后使用 filetrans 模型转录（支持最长 12 小时音频）。

### 额外配置

在 `.env` 中补充 OSS 凭证：
```bash
# 阿里云 OSS 配置
OSS_ACCESS_KEY_ID=你的AccessKeyID
OSS_ACCESS_KEY_SECRET=你的AccessKeySecret
OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
OSS_BUCKET_NAME=your-bucket-name
OSS_PUBLIC_BASE_URL=https://your-bucket-name.oss-cn-shanghai.aliyuncs.com

# Qwen ASR API Key
DASHSCOPE_API_KEY=你的DashscopeKey
```

安装 OSS 依赖：
```bash
uv sync --extra oss
```

获取凭证:
- OSS 密钥: https://ram.console.aliyun.com/manage/ak
- Qwen API Key: https://dashscope.console.aliyun.com/apiKey

### 使用

```bash
uv run process_meeting_video.py /path/to/video.mp4 --output /path/to/output --use-oss
```

额外输出 `video-url.txt`（OSS 公开链接）。

### 分步操作

1. 仅上传:
```bash
uv run upload_to_oss.py /path/to/video.mp4
```

2. 仅转录（需要先有 URL）:
```bash
uv run qwen_asr.py --model filetrans --url "https://..." --srt
```

## 安全注意事项

- `.env` 文件包含敏感信息，已添加到 `.gitignore`
- 不要提交到版本控制，不要分享给他人
- 定期更换密钥

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 转录失败 | 检查 `DASHSCOPE_API_KEY` 是否正确 |
| 上传失败 | 检查 OSS 配置和 AccessKey 权限（需要 PutObject） |
| 格式不支持 | 支持 mp4, mov, avi, mkv, mp3, wav, m4a 等 |
| 依赖缺失 | 运行 `uv sync`（OSS 模式需 `uv sync --extra oss`） |

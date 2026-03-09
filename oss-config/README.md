# OSS 上传和转录配置

## 首次配置

### 1. 创建配置文件

```bash
cd ~/.claude/skills/meeting-to-linear/oss-config
cp .env.example .env  # 从示例创建
```

### 2. 编辑 .env 文件

```bash
# 编辑配置（不要提交到 git）
vim .env
```

填入你的配置：
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

**获取凭证**:
- OSS 密钥: https://ram.console.aliyun.com/manage/ak
- Qwen API Key: https://dashscope.console.aliyun.com/apiKey

### 3. 安装依赖

```bash
cd ~/.claude/skills/meeting-to-linear/oss-config
uv sync
```

## 使用方法

### 完整流程（推荐）

```bash
uv run process_meeting_video.py /path/to/video.mp4 --output /path/to/output
```

### 分步操作

1. 仅上传:
```bash
uv run upload_to_oss.py /path/to/video.mp4
```

2. 仅转录（需要先有 URL）:
```bash
cd ~/.claude/skills/qwen-asr-transcriber/scripts
uv run qwen_asr.py --model filetrans --url "https://..." --srt
```

## 安全注意事项

⚠️ **重要**: `.env` 文件包含敏感信息
- ✅ 已添加到 `.gitignore`
- ✅ 不要提交到版本控制
- ✅ 不要分享给他人
- ✅ 定期更换密钥

## 故障排查

### 上传失败

1. 检查 OSS 配置是否正确
2. 验证 AccessKey 权限（需要 PutObject 权限）
3. 确认 bucket 存在且可访问

### 转录失败

1. 检查 DASHSCOPE_API_KEY 是否正确
2. 确认视频 URL 公开可访问
3. 检查视频格式是否支持（mp4, mov, avi 等）

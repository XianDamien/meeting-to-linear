# Linear API 配置指南

## 快速开始

### 1. 获取 API Key
访问 https://linear.app/settings/account/security

### 2. 配置 API Key（推荐方式）

**创建配置文件 `~/.linear/config`：**
```bash
mkdir -p ~/.linear
echo 'lin_api_你的密钥' > ~/.linear/config
```

**验证配置:**
```bash
cat ~/.linear/config
```

### 3. 安装依赖

```bash
cd ~/.claude/skills/meeting-to-linear
uv pip install -r requirements.txt
```

### 4. 测试连接

```bash
python3 scripts/linear_graphql.py
```

成功输出示例：
```
测试 Linear GraphQL API 连接...

✓ 找到 N 个团队:
  - YourTeam (KEY)
✓ 找到 N 个用户:
  - User A (user_a@example.com)
  - User B (user_b@example.com)
  - ...
```

---

## Best Practice 说明

### 为什么使用 `~/.linear/config`？

**专业工具做法**（像 git、ssh 一样）：

1. **物理隔离** - 配置永远不在项目目录，即使忘记 `.gitignore` 也安全
2. **多项目共用** - 多个 Linear Skill 可共用同一配置
3. **专业感** - 提供标准化的工具体验
4. **简单纯粹** - 文件只包含 API Key，无需解析 `KEY=VALUE` 格式

---

## 安全提示

1. **永远不要提交密钥到 Git**
   确保 `.gitignore` 包含：
   ```
   .env
   .linear
   **/credentials.json
   ```

2. **定期轮换密钥**
   建议每 3-6 个月更换一次

3. **团队协作**
   使用密码管理器（1Password/Bitwarden）共享团队密钥

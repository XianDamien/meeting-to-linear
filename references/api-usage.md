# Linear GraphQL API 用法

## 客户端类

类名：`LinearGraphQL`（位于 `scripts/linear_graphql.py`）

```python
import sys; sys.path.insert(0, 'scripts')
from linear_graphql import LinearGraphQL
client = LinearGraphQL()
```

## 查询方法

### 查询单个 issue
```python
issue = client.get_issue("LAN-296")
# 返回: id, identifier, title, url, description, priority, state, assignee, labels, parent
```

### 查询 issues 列表（检查重复用）
```python
issues = client.get_issues(team_key="LAN", limit=20)
# 返回最近 20 个 issues，含 identifier, title, state, assignee, labels, parent 等
```

### 其他查询
```python
client.get_teams()                          # 所有团队
client.get_team_by_name("YourTeam")          # 按名称查团队
client.get_projects()                       # 所有项目
client.get_users()                          # 所有用户
client.get_issue_labels()                   # workspace 级标签
client.get_issue_labels(team_id="xxx")      # team 级标签
client.get_workflow_states(team_id="xxx")   # 工作流状态
```

## 创建方法

### 创建 issue
```python
issue = client.create_issue(
    team_id="xxx",
    title="Issue 标题",
    description="Markdown 描述",
    priority=2,           # 1=Urgent, 2=High, 3=Medium, 4=Low
    state_id="xxx",
    assignee_id="xxx",
    project_id="xxx",
    label_ids=["uuid1"],
    parent_id="xxx"       # 创建子任务
)
```

### 创建文档
```python
doc = client.create_document(
    project_id="xxx",
    title="文档标题",
    content="Markdown 内容"
)
# 返回: id, slugId, title, url
```

## 更新方法

```python
# 设置父子关系
client.update_issue("LAN-297", parentId="<parent_uuid>")

# 添加标签
client.update_issue("LAN-296", labelIds=["<feature_uuid>", "<test_uuid>"])

# 修改优先级
client.update_issue("LAN-296", priority=1)

# 修改状态
client.update_issue("LAN-296", stateId="<state_uuid>")
```

## Issues JSON 输入格式

`create_linear_issues.py` 接收的 JSON 格式：

```json
[
  {
    "title": "Issue 标题",
    "description": "Markdown 描述内容",
    "priority": "P2",
    "status": "Todo",
    "assignee": "user_a",
    "labels": ["Feature", "Test"]
  }
]
```

- **priority**: `P0`(Urgent) / `P1`(High) / `P2`(Medium) / `P3`(Low)
- **status**: `Todo` / `Backlog` / `In Progress`
- **labels**: 脚本先搜 workspace 级再搜 team 级，无需手动处理 UUID

## 脚本完整参数

```bash
python3 scripts/create_linear_issues.py \
  --issues "issues-input.json" \     # 必需：输入 JSON
  --team "YourTeam" \                 # 团队（默认从 config.json 读取）
  --project "YourProject" \          # 项目（默认从 config.json 读取）
  --output "issues.json" \           # 输出 JSON（用于邮件）
  --parent "LAN-296" \               # 父 issue（创建子任务）
  --document-title "标题" \          # 创建文档
  --document-content "summary.md" \  # 文档内容文件
  --document-only                    # 仅创建文档，跳过 issues
```

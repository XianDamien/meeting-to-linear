# Workspace 标签 ID

> **注意**：标签 ID 因 workspace 不同而异。使用 `get_issue_labels()` 动态查找你自己 workspace 的标签 ID。

| 标签 | UUID（示例）|
|------|------|
| Feature | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| Improvement | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| Tech Debt | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| Bug | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

## 如何获取你的标签 ID

```python
from scripts.linear_graphql import LinearGraphQL

client = LinearGraphQL()
labels = client.get_issue_labels()  # workspace 级标签
for label in labels:
    print(f"{label['name']}: {label['id']}")
```

## 使用方式

标签在 workspace 级别，不在团队级别。创建 issue 后，用 `update_issue(labelIds=[...])` 手动分配。

```python
client.update_issue(
    issue_id="TEAM-XXX",
    labelIds=["your-label-uuid"]  # 替换为实际 UUID
)
```

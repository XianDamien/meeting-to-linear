# 父子 Issues 管理

## 何时整合为父子关系

**应该整合的情况：**
1. 多个 issues 都是同一个大主题的子任务
2. 有明确的总体规划 issue，配合具体实现 issues
3. 相关 issues 需要统一跟踪进度

**示例：**
```
LAN-213: 各个用户权限说明（父 issue - 总体规划）
  ├─ LAN-247: 教师和助教历史查询权限不足（子 issue）
  └─ LAN-248: 看板聚合接口权限问题（子 issue）
```

## 如何设置父子关系

**使用 `scripts/linear_graphql.py` 工具：**
```python
from scripts.linear_graphql import LinearGraphQL

client = LinearGraphQL()

# 设置子 issue 的 parentId
client.update_issue(
    issue_id="子issue的ID或identifier",
    parentId="父issue的ID"
)

# 或者在创建时直接设置
client.create_issue(
    team_id="团队ID",
    title="子任务标题",
    parent_id="父issue的ID"
)
```

## 邮件中的处理规则

**默认规则：**
- 包含所有父 issues
- 包含所有独立 issues
- **不包含子 issues**（除非用户明确要求）

**原因：**
- 子 issues 属于父 issue 的实现细节
- 邮件中只展示顶层任务，避免信息过载
- 接收者可以通过父 issue 链接查看子任务

**微信通知中的展示：**
- 父 issue 后标注：`（包含子任务：LAN-XXX、LAN-YYY）`
- 让读者知道有子任务，但不占用过多空间

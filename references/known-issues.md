# 已知脚本问题

## 5. 标签在团队级别找不到

**原因**：`get_label_by_name(name, team_id)` 只搜索团队级别标签，但 Feature/Improvement/Tech Debt/Bug 等标签存在于 workspace 级别

**表现**：`create_linear_issues.py` 输出 `⚠ 未找到标签: Feature`，创建的 issue 没有标签

**解决**：
1. 先用 `get_issue_labels()`（不传 team_id）获取 workspace 级别所有标签
2. 创建 issue 后，用 `update_issue()` 手动分配 `labelIds`
3. 常用 workspace 标签 ID 参见 `references/label-ids.md`

## 6. ~~create_linear_issues.py 创建文档时会重复创建 issues~~ (已修复)

已添加 `--document-only` 参数。创建文档时使用：
```bash
python3 scripts/create_linear_issues.py \
  --issues "issues-input.json" \
  --document-only \
  --document-title "标题" \
  --document-content "summary.md"
```

## 7. ~~create_linear_issues.py 输出 JSON 优先级/负责人不准确~~ (已修复)

`export_issues_json` 现在从原始输入数据中获取 priority、assignee、labels、status，合并 API 返回的 identifier 和 url。

## 8. ~~邮件脚本 --to 参数只发送给最后一个收件人~~ (已修复)

`--to` 现在支持多次指定和逗号分隔：
```bash
# 多次指定
--to email1@example.com --to email2@example.com

# 逗号分隔
--to "email1@example.com,email2@example.com"

# 混合
--to email1@example.com --to "email2@example.com,email3@example.com"
```

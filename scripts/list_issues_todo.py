#!/usr/bin/env python3
"""
生成需要补充信息的 issues 清单
"""

import os
import sys
from datetime import datetime
from linear_graphql import LinearGraphQL

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from config_loader import get_linear_config


def list_issues_need_attention(client: LinearGraphQL, team_name: str = None):
    """获取需要补充信息的 issues"""
    if team_name is None:
        linear_config = get_linear_config()
        team_name = linear_config.get("team_name", "YourTeam")

    # 获取团队 ID
    team = client.get_team_by_name(team_name)
    if not team:
        raise ValueError(f"未找到团队: {team_name}")

    team_id = team["id"]

    # 获取所有活跃的 issues（排除 completed, canceled, duplicate）
    query = """
    query ListIssues($teamId: ID!, $first: Int!) {
      issues(
        filter: {
          team: { id: { eq: $teamId } }
          state: {
            type: {
              nin: ["completed", "canceled"]
            }
            name: {
              neq: "Duplicate"
            }
          }
        }
        first: $first
        orderBy: updatedAt
      ) {
        nodes {
          id
          identifier
          title
          url
          priority
          priorityLabel
          state {
            name
            type
          }
          assignee {
            id
            name
            displayName
          }
          labels {
            nodes {
              name
            }
          }
          project {
            name
          }
        }
      }
    }
    """

    result = client.execute(query, {"teamId": team_id, "first": 100})
    issues = result.get("issues", {}).get("nodes", [])

    # 分类需要关注的 issues
    no_label_issues = []
    no_assignee_issues = []
    high_priority_no_assignee = []

    for issue in issues:
        labels = issue.get("labels", {}).get("nodes", [])
        assignee = issue.get("assignee")
        priority = issue.get("priorityLabel")

        # 缺少标签
        if not labels:
            no_label_issues.append(issue)

        # 未分配负责人
        if not assignee:
            no_assignee_issues.append(issue)

            # 高优先级未分配
            if priority in ["Urgent", "High"]:
                high_priority_no_assignee.append(issue)

    return {
        "no_label": no_label_issues,
        "no_assignee": no_assignee_issues,
        "high_priority_no_assignee": high_priority_no_assignee
    }


def generate_report(data: dict, output_path: str):
    """生成整理清单报告"""

    report = f"""# Linear Issues 整理清单

**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}

---

## 📋 一、需要补充标签的 Issues ({len(data['no_label'])} 个)

"""

    if data['no_label']:
        for issue in data['no_label']:
            identifier = issue["identifier"]
            title = issue["title"]
            status = issue["state"]["name"]
            priority = issue.get("priorityLabel") or "No priority"
            assignee = issue.get("assignee")
            assignee_name = assignee.get("displayName") or assignee.get("name") if assignee else "未分配"
            url = issue["url"]

            report += f"""### {identifier}: {title}

- **状态**: {status}
- **优先级**: {priority}
- **负责人**: {assignee_name}
- **链接**: {url}
- **建议标签**: _（待确定，可选：Feature, Improvement, Bug, Tech Debt, Arch, Security, Test）_

"""
    else:
        report += "✓ 所有活跃 issues 都已有标签\n\n"

    report += "\n---\n\n"
    report += f"## 👤 二、需要分配负责人的 Issues ({len(data['no_assignee'])} 个)\n\n"

    if data['no_assignee']:
        for issue in data['no_assignee']:
            identifier = issue["identifier"]
            title = issue["title"]
            status = issue["state"]["name"]
            priority = issue.get("priorityLabel") or "No priority"
            labels = issue.get("labels", {}).get("nodes", [])
            label_names = [label["name"] for label in labels]
            label_str = ", ".join(label_names) if label_names else "无标签"
            url = issue["url"]

            priority_marker = "🔴" if priority in ["Urgent", "High"] else ""

            report += f"""### {priority_marker} {identifier}: {title}

- **状态**: {status}
- **优先级**: {priority}
- **标签**: {label_str}
- **链接**: {url}
- **建议负责人**: _（待确定）_

"""
    else:
        report += "✓ 所有活跃 issues 都已分配负责人\n\n"

    report += "\n---\n\n"
    report += f"## ⚠️ 三、高优先级但未分配负责人 ({len(data['high_priority_no_assignee'])} 个)\n\n"

    if data['high_priority_no_assignee']:
        report += "**这些 issues 需要优先处理！**\n\n"
        for issue in data['high_priority_no_assignee']:
            identifier = issue["identifier"]
            title = issue["title"]
            priority = issue.get("priorityLabel")
            url = issue["url"]

            report += f"- 🔴 **{identifier}**: {title} ({priority})\n"
            report += f"  {url}\n\n"
    else:
        report += "✓ 所有高优先级 issues 都已分配负责人\n\n"

    report += "\n---\n\n"
    report += """## 📝 操作指南

### 如何添加标签

使用 `linear_graphql.py` 添加标签：

```python
from linear_graphql import LinearGraphQL

client = LinearGraphQL()

# 获取标签 ID
label = client.get_label_by_name("Feature")  # 或其他标签名

# 更新 issue（注意：需要使用 GraphQL mutation 添加标签）
# 当前 update_issue 不支持 labelIds，需要手动实现
```

### 如何分配负责人

```python
from linear_graphql import LinearGraphQL

client = LinearGraphQL()

# 获取用户 ID
user = client.get_user_by_name("user_a")

# 分配负责人
client.update_issue(
    issue_id="LAN-XXX",
    assigneeId=user["id"]
)
```

### 可用标签

- **Feature**: 新功能
- **Improvement**: 功能改进
- **Bug**: 缺陷修复
- **Tech Debt**: 技术债务
- **Arch**: 架构设计
- **Security**: 安全问题
- **Test**: 测试相关

### 可用负责人（从 config.json 的 team_members 配置）

- **user_a**: 前端开发
- **user_b**: 后端开发
- **user_c**: 产品经理
- **user_d**: 项目经理
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✓ 整理清单已生成: {output_path}")


def main():
    client = LinearGraphQL()

    print("正在分析 issues，查找需要补充信息的条目...")

    data = list_issues_need_attention(client)

    print(f"\n发现:")
    print(f"  - 缺少标签: {len(data['no_label'])} 个")
    print(f"  - 未分配负责人: {len(data['no_assignee'])} 个")
    print(f"  - 高优先级未分配: {len(data['high_priority_no_assignee'])} 个")

    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "..", "reports", f"{timestamp}-issues-todo.md")

    generate_report(data, output_path)

    print(f"\n报告路径: {output_path}")


if __name__ == "__main__":
    main()

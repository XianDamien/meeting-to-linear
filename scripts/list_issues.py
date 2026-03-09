#!/usr/bin/env python3
"""
获取 Linear issues 并生成报告
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from linear_graphql import LinearGraphQL

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from config_loader import get_linear_config


def list_issues(
    client: LinearGraphQL,
    team_name: str = None,
    limit: int = 20,
    include_completed: bool = False
) -> List[Dict]:
    """
    获取 issues 列表

    Args:
        client: LinearGraphQL 客户端
        team_name: 团队名称
        limit: 获取数量
        include_completed: 是否包含已完成的 issues

    Returns:
        List[Dict]: issues 列表
    """
    if team_name is None:
        linear_config = get_linear_config()
        team_name = linear_config.get("team_name", "YourTeam")

    # 获取团队 ID
    team = client.get_team_by_name(team_name)
    if not team:
        raise ValueError(f"未找到团队: {team_name}")

    team_id = team["id"]

    # 构建 GraphQL 查询
    query = """
    query ListIssues($teamId: ID!, $first: Int!, $includeCompleted: Boolean!) {
      issues(
        filter: {
          team: { id: { eq: $teamId } }
          state: { type: { neq: "completed" } }
        }
        first: $first
        orderBy: updatedAt
      ) @skip(if: $includeCompleted) {
        nodes {
          id
          identifier
          title
          description
          url
          createdAt
          updatedAt
          priority
          priorityLabel
          state {
            id
            name
            type
          }
          assignee {
            id
            name
            displayName
            email
          }
          labels {
            nodes {
              id
              name
            }
          }
          parent {
            id
            identifier
            title
          }
          project {
            id
            name
          }
        }
      }
      allIssues: issues(
        filter: {
          team: { id: { eq: $teamId } }
        }
        first: $first
        orderBy: updatedAt
      ) @include(if: $includeCompleted) {
        nodes {
          id
          identifier
          title
          description
          url
          createdAt
          updatedAt
          priority
          priorityLabel
          state {
            id
            name
            type
          }
          assignee {
            id
            name
            displayName
            email
          }
          labels {
            nodes {
              id
              name
            }
          }
          parent {
            id
            identifier
            title
          }
          project {
            id
            name
          }
        }
      }
    }
    """

    variables = {
        "teamId": team_id,
        "first": limit,
        "includeCompleted": include_completed
    }

    result = client.execute(query, variables)

    if include_completed:
        return result.get("allIssues", {}).get("nodes", [])
    else:
        return result.get("issues", {}).get("nodes", [])


def generate_markdown_report(issues: List[Dict], output_path: str):
    """
    生成 Markdown 格式的报告

    Args:
        issues: issues 列表
        output_path: 输出文件路径
    """
    # 统计数据
    total = len(issues)
    by_status = {}
    by_priority = {}
    by_assignee = {}
    by_label = {}
    parent_issues = []
    child_issues = []

    for issue in issues:
        # 按状态统计
        status = issue["state"]["name"]
        by_status[status] = by_status.get(status, 0) + 1

        # 按优先级统计
        priority = issue.get("priorityLabel") or "No priority"
        by_priority[priority] = by_priority.get(priority, 0) + 1

        # 按负责人统计
        assignee = issue.get("assignee")
        if assignee:
            assignee_name = assignee.get("displayName") or assignee.get("name")
            by_assignee[assignee_name] = by_assignee.get(assignee_name, 0) + 1
        else:
            by_assignee["未分配"] = by_assignee.get("未分配", 0) + 1

        # 按标签统计
        labels = issue.get("labels", {}).get("nodes", [])
        for label in labels:
            label_name = label["name"]
            by_label[label_name] = by_label.get(label_name, 0) + 1

        # 区分父子 issues
        if issue.get("parent"):
            child_issues.append(issue)
        else:
            parent_issues.append(issue)

    # 生成报告
    report = f"""# Linear Issues 整理报告

**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}

**总计**: {total} 个 issues

---

## 📊 统计概览

### 按状态分布

| 状态 | 数量 |
|------|------|
"""

    for status, count in sorted(by_status.items(), key=lambda x: x[1], reverse=True):
        report += f"| {status} | {count} |\n"

    report += "\n### 按优先级分布\n\n| 优先级 | 数量 |\n|--------|------|\n"

    priority_order = {"Urgent": 1, "High": 2, "Medium": 3, "Low": 4, "No priority": 5}
    for priority, count in sorted(by_priority.items(), key=lambda x: priority_order.get(x[0], 6)):
        report += f"| {priority} | {count} |\n"

    report += "\n### 按负责人分布\n\n| 负责人 | 数量 |\n|--------|------|\n"

    for assignee, count in sorted(by_assignee.items(), key=lambda x: x[1], reverse=True):
        report += f"| {assignee} | {count} |\n"

    report += "\n### 按标签分布\n\n| 标签 | 数量 |\n|------|------|\n"

    for label, count in sorted(by_label.items(), key=lambda x: x[1], reverse=True):
        report += f"| {label} | {count} |\n"

    # 父子 issues 统计
    report += f"\n---\n\n## 🔗 父子 Issues 统计\n\n"
    report += f"- **父 issues**: {len(parent_issues)} 个\n"
    report += f"- **子 issues**: {len(child_issues)} 个\n"

    # 详细列表
    report += "\n---\n\n## 📝 Issues 详细列表\n\n"

    # 按优先级和状态分组
    groups = {
        "🚨 高优先级 (Urgent/High)": [],
        "📌 中优先级 (Medium)": [],
        "📋 低优先级 (Low/No priority)": []
    }

    for issue in parent_issues:
        priority = issue.get("priorityLabel") or "No priority"
        if priority in ["Urgent", "High"]:
            groups["🚨 高优先级 (Urgent/High)"].append(issue)
        elif priority == "Medium":
            groups["📌 中优先级 (Medium)"].append(issue)
        else:
            groups["📋 低优先级 (Low/No priority)"].append(issue)

    for group_name, group_issues in groups.items():
        if not group_issues:
            continue

        report += f"\n### {group_name} ({len(group_issues)} 个)\n\n"

        for issue in group_issues:
            identifier = issue["identifier"]
            title = issue["title"]
            status = issue["state"]["name"]
            priority = issue.get("priorityLabel") or "No priority"
            assignee = issue.get("assignee")
            assignee_name = "未分配"
            if assignee:
                assignee_name = assignee.get("displayName") or assignee.get("name")

            labels = issue.get("labels", {}).get("nodes", [])
            label_names = [label["name"] for label in labels]
            label_str = ", ".join(label_names) if label_names else "无标签"

            url = issue["url"]

            # 查找子 issues
            children = [c for c in child_issues if c.get("parent", {}).get("id") == issue["id"]]

            report += f"#### [{identifier}] {title}\n\n"
            report += f"- **状态**: {status}\n"
            report += f"- **优先级**: {priority}\n"
            report += f"- **负责人**: {assignee_name}\n"
            report += f"- **标签**: {label_str}\n"
            report += f"- **链接**: {url}\n"

            if children:
                report += f"- **子任务** ({len(children)} 个):\n"
                for child in children:
                    child_id = child["identifier"]
                    child_title = child["title"]
                    child_status = child["state"]["name"]
                    report += f"  - [{child_id}] {child_title} ({child_status})\n"

            report += "\n"

    # 独立的子 issues（如果父 issue 不在列表中）
    orphan_children = [c for c in child_issues if c.get("parent", {}).get("id") not in [i["id"] for i in parent_issues]]

    if orphan_children:
        report += f"\n### 📎 其他子任务 ({len(orphan_children)} 个)\n\n"
        for issue in orphan_children:
            identifier = issue["identifier"]
            title = issue["title"]
            status = issue["state"]["name"]
            parent = issue.get("parent", {})
            parent_id = parent.get("identifier", "未知")
            parent_title = parent.get("title", "")

            report += f"- [{identifier}] {title} ({status})\n"
            report += f"  - 父任务: [{parent_id}] {parent_title}\n"

    report += "\n---\n\n## 🎯 整理建议\n\n"
    report += "### 需要关注的 Issues\n\n"

    # 高优先级未分配
    high_priority_unassigned = [
        i for i in parent_issues
        if i.get("priorityLabel") in ["Urgent", "High"] and not i.get("assignee")
    ]

    if high_priority_unassigned:
        report += "#### 高优先级但未分配负责人\n\n"
        for issue in high_priority_unassigned:
            report += f"- [{issue['identifier']}] {issue['title']}\n"
        report += "\n"

    # 无标签 issues
    no_label_issues = [
        i for i in parent_issues
        if not i.get("labels", {}).get("nodes")
    ]

    if no_label_issues:
        report += "#### 缺少标签\n\n"
        for issue in no_label_issues:
            report += f"- [{issue['identifier']}] {issue['title']}\n"
        report += "\n"

    # 无项目 issues
    no_project_issues = [
        i for i in parent_issues
        if not i.get("project")
    ]

    if no_project_issues:
        report += "#### 未关联项目\n\n"
        for issue in no_project_issues:
            report += f"- [{issue['identifier']}] {issue['title']}\n"
        report += "\n"

    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✓ 报告已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="获取 Linear issues 并生成报告")
    parser.add_argument("--team", default=None, help="团队名称（默认从 config.json 读取）")
    parser.add_argument("--limit", type=int, default=20, help="获取数量")
    parser.add_argument("--include-completed", action="store_true", help="包含已完成的 issues")
    parser.add_argument("--output", help="输出文件路径")

    args = parser.parse_args()

    # 初始化客户端
    client = LinearGraphQL()

    print(f"正在获取 {args.team} 团队的最近 {args.limit} 个 issues...")

    # 获取 issues
    issues = list_issues(
        client,
        team_name=args.team,
        limit=args.limit,
        include_completed=args.include_completed
    )

    print(f"✓ 获取到 {len(issues)} 个 issues")

    # 生成报告
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.output = os.path.join(script_dir, "..", "reports", f"{timestamp}-issues-report.md")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    generate_markdown_report(issues, args.output)

    print(f"\n报告路径: {args.output}")


if __name__ == "__main__":
    main()

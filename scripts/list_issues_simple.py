#!/usr/bin/env python3
"""
获取 Linear issues 并按创建时间生成简单列表
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
    limit: int = 50,
    include_completed: bool = False
) -> List[Dict]:
    """
    获取 issues 列表，按创建时间排序

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

    # 构建 GraphQL 查询 - 按创建时间排序
    if include_completed:
        filter_clause = 'filter: { team: { id: { eq: $teamId } } }'
    else:
        filter_clause = 'filter: { team: { id: { eq: $teamId } }, state: { type: { neq: "completed" } } }'

    query = f"""
    query ListIssues($teamId: ID!, $first: Int!) {{
      issues(
        {filter_clause}
        first: $first
        orderBy: createdAt
      ) {{
        nodes {{
          id
          identifier
          title
          description
          url
          createdAt
          updatedAt
          priority
          priorityLabel
          state {{
            id
            name
            type
          }}
          assignee {{
            id
            name
            displayName
            email
          }}
          labels {{
            nodes {{
              id
              name
            }}
          }}
          parent {{
            id
            identifier
            title
          }}
          project {{
            id
            name
          }}
        }}
      }}
    }}
    """

    variables = {
        "teamId": team_id,
        "first": limit
    }

    result = client.execute(query, variables)
    return result.get("issues", {}).get("nodes", [])


def find_duplicate_issues(issues: List[Dict]) -> Dict[str, List[Dict]]:
    """
    查找可能重复的 issues（基于标题相似度）

    Args:
        issues: issues 列表

    Returns:
        Dict: 分组的重复 issues
    """
    from difflib import SequenceMatcher

    duplicates = {}

    for i, issue1 in enumerate(issues):
        title1 = issue1["title"].lower()
        similar_issues = [issue1]

        for j, issue2 in enumerate(issues):
            if i >= j:
                continue

            title2 = issue2["title"].lower()
            similarity = SequenceMatcher(None, title1, title2).ratio()

            # 如果相似度超过 70%，认为可能重复
            if similarity > 0.7:
                similar_issues.append(issue2)

        if len(similar_issues) > 1:
            # 使用第一个 issue 的 identifier 作为 key
            key = issue1["identifier"]
            if key not in duplicates:
                duplicates[key] = similar_issues

    return duplicates


def generate_simple_list(issues: List[Dict], output_path: str):
    """
    生成简单的时间序列列表

    Args:
        issues: issues 列表
        output_path: 输出文件路径
    """
    # 按创建时间排序
    sorted_issues = sorted(issues, key=lambda x: x["createdAt"])

    # 查找可能重复的 issues
    duplicates = find_duplicate_issues(sorted_issues)

    report = f"""# Linear Issues 时间序列列表

**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}

**总计**: {len(sorted_issues)} 个 issues

---

## 📋 按创建时间排序的 Issues

"""

    for issue in sorted_issues:
        identifier = issue["identifier"]
        title = issue["title"]
        status = issue["state"]["name"]
        priority = issue.get("priorityLabel") or "No priority"

        assignee = issue.get("assignee")
        if assignee:
            assignee_name = assignee.get("displayName") or assignee.get("name")
        else:
            assignee_name = "未分配"

        labels = issue.get("labels", {}).get("nodes", [])
        label_names = [label["name"] for label in labels]
        label_str = ", ".join(label_names) if label_names else "无标签"

        created_at = datetime.fromisoformat(issue["createdAt"].replace('Z', '+00:00'))
        created_str = created_at.strftime("%Y-%m-%d")

        # 获取描述的前100个字符作为概括
        description = issue.get("description", "")
        if description:
            # 移除 markdown 格式
            summary = description.replace('\n', ' ').replace('#', '').strip()
            if len(summary) > 100:
                summary = summary[:100] + "..."
        else:
            summary = "（无描述）"

        # 标记父子关系
        parent = issue.get("parent")
        if parent:
            parent_marker = f" [子任务 ← {parent['identifier']}]"
        else:
            parent_marker = ""

        report += f"""### {identifier}: {title}

- **创建时间**: {created_str}
- **状态**: {status} | **优先级**: {priority} | **负责人**: {assignee_name}
- **标签**: {label_str}{parent_marker}
- **概括**: {summary}
- **链接**: {issue["url"]}

"""

    # 添加可能重复的 issues
    if duplicates:
        report += "\n---\n\n## ⚠️ 可能重复的 Issues\n\n"
        report += "以下 issues 标题相似度较高（>70%），请检查是否重复：\n\n"

        processed = set()
        for key, similar_issues in duplicates.items():
            # 避免重复输出同一组
            identifiers = tuple(sorted([i["identifier"] for i in similar_issues]))
            if identifiers in processed:
                continue
            processed.add(identifiers)

            report += f"**相似组 {len(processed)}**:\n"
            for issue in similar_issues:
                report += f"- [{issue['identifier']}] {issue['title']} ({issue['state']['name']})\n"
            report += "\n"

    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✓ 简单列表已生成: {output_path}")

    if duplicates:
        print(f"\n⚠️  发现 {len(duplicates)} 组可能重复的 issues，请查看报告")


def main():
    parser = argparse.ArgumentParser(description="获取 Linear issues 并按创建时间生成简单列表")
    parser.add_argument("--team", default=None, help="团队名称（默认从 config.json 读取）")
    parser.add_argument("--limit", type=int, default=50, help="获取数量")
    parser.add_argument("--include-completed", action="store_true", help="包含已完成的 issues")
    parser.add_argument("--output", help="输出文件路径")

    args = parser.parse_args()

    # 初始化客户端
    client = LinearGraphQL()

    print(f"正在获取 {args.team} 团队的最近 {args.limit} 个 issues（按创建时间排序）...")

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
        args.output = os.path.join(script_dir, "..", "reports", f"{timestamp}-issues-simple-list.md")

    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    generate_simple_list(issues, args.output)

    print(f"\n报告路径: {args.output}")


if __name__ == "__main__":
    main()

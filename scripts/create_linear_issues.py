#!/usr/bin/env python3
"""
批量创建 Linear Issues 和 Document
使用 GraphQL API 直接调用，替代 MCP
"""

import json
import sys
import os
from typing import List, Dict, Optional
from linear_graphql import LinearGraphQL

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from config_loader import get_linear_config


class LinearIssueCreator:
    """Linear Issues 批量创建工具"""

    def __init__(self, team_name: Optional[str] = None, project_name: Optional[str] = None):
        """
        初始化

        Args:
            team_name: 团队名称
            project_name: 项目名称
        """
        self.client = LinearGraphQL()
        linear_config = get_linear_config()
        self.team_name = team_name or linear_config.get("team_name", "YourTeam")
        self.project_name = project_name or linear_config.get("project_name", "YourProject")

        # 缓存 IDs
        self._team_id = None
        self._project_id = None
        self._users_cache = {}
        self._states_cache = {}
        self._labels_cache = {}

    def _get_team_id(self) -> str:
        """获取团队 ID（缓存）"""
        if not self._team_id:
            team = self.client.get_team_by_name(self.team_name)
            if not team:
                raise ValueError(f"未找到团队: {self.team_name}")
            self._team_id = team["id"]
            print(f"✓ 找到团队: {team['name']} ({team['key']})")
        return self._team_id

    def _get_project_id(self) -> str:
        """获取项目 ID（缓存）"""
        if not self._project_id:
            team_id = self._get_team_id()
            project = self.client.get_project_by_name(self.project_name, team_id)
            if not project:
                raise ValueError(f"未找到项目: {self.project_name}")
            self._project_id = project["id"]
            print(f"✓ 找到项目: {project['name']}")
        return self._project_id

    def _get_user_id(self, username: str) -> Optional[str]:
        """获取用户 ID（缓存）"""
        if username not in self._users_cache:
            user = self.client.get_user_by_name(username)
            if user:
                self._users_cache[username] = user["id"]
                print(f"✓ 找到用户: {username} → {user.get('displayName', user.get('name'))}")
            else:
                print(f"⚠ 未找到用户: {username}")
                self._users_cache[username] = None
        return self._users_cache[username]

    def _get_state_id(self, state_name: str) -> Optional[str]:
        """获取状态 ID（缓存）"""
        if state_name not in self._states_cache:
            team_id = self._get_team_id()
            state = self.client.get_state_by_name(team_id, state_name)
            if state:
                self._states_cache[state_name] = state["id"]
                print(f"✓ 找到状态: {state_name} → {state['name']}")
            else:
                print(f"⚠ 未找到状态: {state_name}，将使用默认状态")
                self._states_cache[state_name] = None
        return self._states_cache[state_name]

    def _get_label_ids(self, label_names: List[str]) -> List[str]:
        """获取标签 IDs（缓存）

        标签分两级：workspace 级（Feature, Improvement, Bug, Tech Debt, Arch）和 team 级。
        先搜 workspace 级，未找到再搜 team 级。
        """
        team_id = self._get_team_id()
        label_ids = []

        for label_name in label_names:
            if label_name not in self._labels_cache:
                # 先搜 workspace 级（不传 team_id）
                label = self.client.get_label_by_name(label_name)
                if not label:
                    # 再搜 team 级
                    label = self.client.get_label_by_name(label_name, team_id)
                if label:
                    self._labels_cache[label_name] = label["id"]
                    print(f"✓ 找到标签: {label_name}")
                else:
                    print(f"⚠ 未找到标签: {label_name}")
                    self._labels_cache[label_name] = None

            label_id = self._labels_cache[label_name]
            if label_id:
                label_ids.append(label_id)

        return label_ids

    def create_issue_from_dict(self, issue_data: Dict) -> Dict:
        """
        从字典数据创建 Issue

        Args:
            issue_data: Issue 数据字典，支持的字段：
                - title: 标题（必需）
                - description: 描述
                - priority: 优先级名称（P0/P1/P2/P3）或数值（1/2/3/4）
                - status: 状态名称（Todo/Backlog/In Progress 等）
                - assignee: 负责人用户名
                - labels: 标签名称列表
                - parent_id: 父 Issue ID（用于创建子任务）

        Returns:
            Dict: 创建的 Issue 信息
        """
        team_id = self._get_team_id()
        project_id = self._get_project_id()

        # 解析优先级
        priority = None
        if "priority" in issue_data:
            priority_value = issue_data["priority"]
            if isinstance(priority_value, str):
                # 映射 P0/P1/P2/P3 到数值
                priority_map = {"P0": 1, "P1": 2, "P2": 3, "P3": 4}
                priority = priority_map.get(priority_value.upper(), 3)
            else:
                priority = priority_value

        # 解析状态
        state_id = None
        if "status" in issue_data:
            state_id = self._get_state_id(issue_data["status"])

        # 解析负责人
        assignee_id = None
        if "assignee" in issue_data:
            assignee_id = self._get_user_id(issue_data["assignee"])

        # 解析标签
        label_ids = None
        if "labels" in issue_data and issue_data["labels"]:
            label_ids = self._get_label_ids(issue_data["labels"])

        # 创建 Issue
        issue = self.client.create_issue(
            team_id=team_id,
            title=issue_data["title"],
            description=issue_data.get("description"),
            priority=priority,
            state_id=state_id,
            assignee_id=assignee_id,
            project_id=project_id,
            label_ids=label_ids,
            parent_id=issue_data.get("parent_id")
        )

        return issue

    def create_issues_batch(self, issues_data: List[Dict]) -> List[Dict]:
        """
        批量创建 Issues

        Args:
            issues_data: Issue 数据列表

        Returns:
            List[Dict]: 创建的 Issues 信息列表
        """
        created_issues = []

        print(f"\n开始批量创建 {len(issues_data)} 个 Issues...")

        for i, issue_data in enumerate(issues_data, 1):
            try:
                print(f"\n[{i}/{len(issues_data)}] 创建 Issue: {issue_data.get('title', 'N/A')}")
                issue = self.create_issue_from_dict(issue_data)
                created_issues.append(issue)
                print(f"✓ 创建成功: {issue['identifier']} - {issue['title']}")
                print(f"  URL: {issue['url']}")
            except Exception as e:
                print(f"✗ 创建失败: {e}")
                continue

        print(f"\n✓ 批量创建完成: {len(created_issues)}/{len(issues_data)} 成功")
        return created_issues

    def create_document(
        self,
        title: str,
        content: str,
        icon: Optional[str] = None,
        color: Optional[str] = None
    ) -> Dict:
        """
        创建 Linear 文档

        Args:
            title: 文档标题
            content: 文档内容（Markdown）
            icon: 图标 emoji
            color: 颜色（hex）

        Returns:
            Dict: 创建的文档信息
        """
        project_id = self._get_project_id()

        print(f"\n创建文档: {title}")
        document = self.client.create_document(
            project_id=project_id,
            title=title,
            content=content,
            icon=icon,
            color=color
        )

        print(f"✓ 文档创建成功: {document['title']}")
        print(f"  URL: {document['url']}")
        print(f"  Slug ID: {document['slugId']}")

        return document


def export_issues_json(api_issues: List[Dict], input_issues: List[Dict], output_path: str):
    """
    导出 Issues 为 JSON 格式（用于邮件通知）

    合并 API 返回的 identifier/url 与原始输入的 priority/assignee/labels/status。

    Args:
        api_issues: Linear API 返回的 Issue 列表（含 identifier, title, url）
        input_issues: 原始输入的 Issue 数据列表（含 priority, assignee, labels, status）
        output_path: 输出文件路径
    """
    # 优先级名称映射
    priority_name_map = {1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}
    priority_str_map = {"P0": 1, "P1": 2, "P2": 3, "P3": 4}

    issues_data = []
    for i, api_issue in enumerate(api_issues):
        # 获取对应的原始输入数据
        input_data = input_issues[i] if i < len(input_issues) else {}

        # 解析优先级：从原始输入获取
        raw_priority = input_data.get("priority", "P2")
        if isinstance(raw_priority, str):
            p_value = priority_str_map.get(raw_priority.upper(), 3)
        elif isinstance(raw_priority, dict):
            p_value = raw_priority.get("value", 3)
        else:
            p_value = raw_priority if isinstance(raw_priority, int) else 3
        priority = {"value": p_value, "name": priority_name_map.get(p_value, "Medium")}

        issues_data.append({
            "identifier": api_issue["identifier"],
            "title": api_issue["title"],
            "url": api_issue["url"],
            "priority": priority,
            "assignee": input_data.get("assignee", "unknown"),
            "labels": input_data.get("labels", ["Feature"]),
            "status": input_data.get("status", "Todo")
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(issues_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Issues JSON 已导出: {output_path}")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='批量创建 Linear Issues 和 Document')
    parser.add_argument('--issues', required=True, help='Issues 数据 JSON 文件路径')
    parser.add_argument('--team', help='团队名称（默认从 config.json 读取）')
    parser.add_argument('--project', help='项目名称（默认从 config.json 读取）')
    parser.add_argument('--document-title', help='文档标题（可选）')
    parser.add_argument('--document-content', help='文档内容文件路径（可选）')
    parser.add_argument('--document-only', action='store_true',
                        help='仅创建文档，跳过 issues 创建（避免重复创建）')
    parser.add_argument('--output', help='输出 Issues JSON 文件路径（用于邮件通知）')
    parser.add_argument('--parent', help='父 Issue identifier（如 LAN-296），创建的 issues 将作为其子任务')

    args = parser.parse_args()

    # 读取 Issues 数据
    try:
        with open(args.issues, 'r', encoding='utf-8') as f:
            issues_data = json.load(f)
    except FileNotFoundError:
        print(f"✗ 错误：找不到文件 {args.issues}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ 错误：JSON 格式无效: {e}")
        sys.exit(1)

    # 初始化创建器
    creator = LinearIssueCreator(team_name=args.team, project_name=args.project)

    # 批量创建 Issues（除非 --document-only）
    created_issues = []
    if not args.document_only:
        # 如果指定了 --parent，解析父 issue ID 并注入到每个 issue
        if args.parent:
            parent_issue = creator.client.get_issue(args.parent)
            parent_id = parent_issue["id"]
            print(f"✓ 找到父 Issue: {args.parent} (id: {parent_id})")
            for issue in issues_data:
                issue["parent_id"] = parent_id

        created_issues = creator.create_issues_batch(issues_data)

        # 导出 JSON（如果指定输出路径）
        if args.output:
            export_issues_json(created_issues, issues_data, args.output)
    else:
        print("\n⏭ 跳过 issues 创建（--document-only 模式）")

    # 创建文档（如果提供）
    if args.document_title and args.document_content:
        if os.path.exists(args.document_content):
            with open(args.document_content, 'r', encoding='utf-8') as f:
                content = f.read()
            creator.create_document(
                title=args.document_title,
                content=content
            )
        else:
            print(f"⚠ 文档内容文件不存在: {args.document_content}")

    print("\n✓ 所有操作完成")


if __name__ == "__main__":
    main()

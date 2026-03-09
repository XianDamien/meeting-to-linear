#!/usr/bin/env python3
"""
Linear GraphQL API 工具函数
直接调用 Linear GraphQL API，替代 MCP
"""

import os
import requests
from typing import Dict, List, Optional


class LinearGraphQL:
    """Linear GraphQL API 客户端"""

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        """
        初始化 Linear GraphQL 客户端

        Args:
            api_key: Linear API Key（如果不提供，则从 ~/.linear/config 读取）
            endpoint: GraphQL 端点（默认 https://api.linear.app/graphql）
        """
        self.api_key = api_key or self._load_api_key()
        self.endpoint = endpoint or "https://api.linear.app/graphql"
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }

    def _load_api_key(self) -> str:
        """从 ~/.linear/config 读取 API Key"""
        config_path = os.path.expanduser("~/.linear/config")

        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key and key != 'your_api_key_here':
                    return key

        # 未找到配置，给出清晰的配置指引
        config_dir = os.path.expanduser("~/.linear")
        raise ValueError(
            "\n" + "=" * 60 + "\n"
            "❌ 未找到 Linear API Key！\n\n"
            "请配置 API Key：\n\n"
            f"  mkdir -p {config_dir}\n"
            f"  echo 'lin_api_xxxxxx' > {config_path}\n\n"
            "获取 API Key：https://linear.app/settings/account/security\n"
            + "=" * 60
        )

    def execute(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        执行 GraphQL 查询

        Args:
            query: GraphQL 查询字符串
            variables: 查询变量

        Returns:
            Dict: API 响应数据

        Raises:
            Exception: API 请求失败
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(
            self.endpoint,
            headers=self.headers,
            json=payload
        )

        if response.status_code != 200:
            raise Exception(
                f"GraphQL 请求失败: {response.status_code}\n"
                f"响应: {response.text}"
            )

        result = response.json()

        if "errors" in result:
            errors = result["errors"]
            error_messages = "\n".join([e.get("message", str(e)) for e in errors])
            raise Exception(f"GraphQL 错误:\n{error_messages}")

        return result.get("data", {})

    # ==================== 查询方法 ====================

    def get_issue(self, identifier: str) -> Dict:
        """
        根据 identifier（如 LAN-296）获取单个 Issue

        Args:
            identifier: Issue identifier，格式为 TEAM_KEY-NUMBER（如 LAN-296）

        Returns:
            Dict: Issue 信息（id, identifier, title, url, description, priority, status 等）
        """
        # 从 identifier 解析 team key 和 number
        parts = identifier.rsplit("-", 1)
        if len(parts) != 2:
            raise ValueError(f"无效的 identifier 格式: {identifier}，期望格式如 LAN-296")
        team_key, number_str = parts
        try:
            number = int(number_str)
        except ValueError:
            raise ValueError(f"无效的 issue 编号: {number_str}")

        query = """
        query GetIssue($number: Float!, $teamKey: String!) {
          issues(filter: { number: { eq: $number }, team: { key: { eq: $teamKey } } }, first: 1) {
            nodes {
              id
              identifier
              title
              url
              description
              priority
              state { id name }
              assignee { id name displayName }
              labels { nodes { id name } }
              parent { id identifier }
            }
          }
        }
        """
        result = self.execute(query, {"number": number, "teamKey": team_key})
        nodes = result.get("issues", {}).get("nodes", [])
        if not nodes:
            raise ValueError(f"未找到 Issue: {identifier}")
        return nodes[0]

    def get_issues(
        self,
        team_key: Optional[str] = None,
        project_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        查询 Issues 列表（用于检查重复和查看现有 issues）

        Args:
            team_key: 团队 key（如 LAN），不传则查询所有团队
            project_name: 项目名称过滤
            status: 状态名称过滤（如 Todo, In Progress）
            limit: 返回数量上限（默认 20）

        Returns:
            List[Dict]: Issue 列表
        """
        # 构建 filter
        filter_parts = []
        variables = {"limit": limit}

        if team_key:
            filter_parts.append('team: { key: { eq: $teamKey } }')
            variables["teamKey"] = team_key

        filter_str = ""
        if filter_parts:
            filter_str = f"filter: {{ {', '.join(filter_parts)} }},"

        query = f"""
        query GetIssues($limit: Int!{', $teamKey: String!' if team_key else ''}) {{
          issues({filter_str} first: $limit, orderBy: createdAt) {{
            nodes {{
              id
              identifier
              title
              url
              priority
              state {{ name }}
              assignee {{ name displayName }}
              labels {{ nodes {{ name }} }}
              parent {{ id identifier }}
              createdAt
            }}
          }}
        }}
        """
        result = self.execute(query, variables)
        return result.get("issues", {}).get("nodes", [])

    def get_teams(self) -> List[Dict]:
        """获取所有团队"""
        query = """
        query GetTeams {
          teams {
            nodes {
              id
              name
              key
            }
          }
        }
        """
        result = self.execute(query)
        return result.get("teams", {}).get("nodes", [])

    def get_team_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取团队"""
        teams = self.get_teams()
        for team in teams:
            if team["name"] == name or team["key"] == name:
                return team
        return None

    def get_projects(self) -> List[Dict]:
        """获取项目列表"""
        query = """
        query GetProjects {
          projects {
            nodes {
              id
              name
              slugId
            }
          }
        }
        """
        result = self.execute(query)
        return result.get("projects", {}).get("nodes", [])

    def get_project_by_name(self, name: str, team_id: Optional[str] = None) -> Optional[Dict]:
        """根据名称获取项目"""
        projects = self.get_projects()
        for project in projects:
            if project["name"] == name:
                return project
        return None

    def get_workflow_states(self, team_id: str) -> List[Dict]:
        """获取团队的工作流状态"""
        query = """
        query GetWorkflowStates($teamId: ID!) {
          workflowStates(filter: {team: {id: {eq: $teamId}}}) {
            nodes {
              id
              name
              type
            }
          }
        }
        """
        result = self.execute(query, {"teamId": team_id})
        return result.get("workflowStates", {}).get("nodes", [])

    def get_state_by_name(self, team_id: str, name: str) -> Optional[Dict]:
        """根据名称获取状态"""
        states = self.get_workflow_states(team_id)
        for state in states:
            if state["name"].lower() == name.lower() or state["type"].lower() == name.lower():
                return state
        return None

    def get_users(self) -> List[Dict]:
        """获取所有用户"""
        query = """
        query GetUsers {
          users {
            nodes {
              id
              name
              displayName
              email
            }
          }
        }
        """
        result = self.execute(query)
        return result.get("users", {}).get("nodes", [])

    def get_user_by_name(self, name: str) -> Optional[Dict]:
        """根据用户名、显示名或邮箱获取用户"""
        users = self.get_users()
        name_lower = name.lower()
        for user in users:
            if (user.get("name", "").lower() == name_lower or
                user.get("displayName", "").lower() == name_lower or
                user.get("email", "").lower() == name_lower):
                return user
        return None

    def get_issue_labels(self, team_id: Optional[str] = None) -> List[Dict]:
        """获取 Issue 标签"""
        query = """
        query GetIssueLabels($filter: IssueLabelFilter) {
          issueLabels(filter: $filter) {
            nodes {
              id
              name
            }
          }
        }
        """
        variables = {}
        if team_id:
            variables["filter"] = {"team": {"id": {"eq": team_id}}}

        result = self.execute(query, variables)
        return result.get("issueLabels", {}).get("nodes", [])

    def get_label_by_name(self, name: str, team_id: Optional[str] = None) -> Optional[Dict]:
        """根据名称获取标签"""
        labels = self.get_issue_labels(team_id)
        for label in labels:
            if label["name"].lower() == name.lower():
                return label
        return None

    # ==================== 创建方法 ====================

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        state_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        project_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        parent_id: Optional[str] = None
    ) -> Dict:
        """
        创建 Issue

        Args:
            team_id: 团队 ID
            title: Issue 标题
            description: Issue 描述（Markdown）
            priority: 优先级（0=None, 1=Urgent, 2=High, 3=Medium, 4=Low）
            state_id: 状态 ID
            assignee_id: 负责人 ID
            project_id: 项目 ID
            label_ids: 标签 ID 列表
            parent_id: 父 Issue ID（用于创建子任务）

        Returns:
            Dict: 创建的 Issue 信息，包含 id, identifier, url
        """
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue {
              id
              identifier
              title
              url
            }
          }
        }
        """

        input_data = {
            "teamId": team_id,
            "title": title
        }

        if description:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if state_id:
            input_data["stateId"] = state_id
        if assignee_id:
            input_data["assigneeId"] = assignee_id
        if project_id:
            input_data["projectId"] = project_id
        if label_ids:
            input_data["labelIds"] = label_ids
        if parent_id:
            input_data["parentId"] = parent_id

        result = self.execute(mutation, {"input": input_data})

        if not result.get("issueCreate", {}).get("success"):
            raise Exception("创建 Issue 失败")

        return result["issueCreate"]["issue"]

    def create_document(
        self,
        project_id: str,
        title: str,
        content: str,
        icon: Optional[str] = None,
        color: Optional[str] = None
    ) -> Dict:
        """
        创建 Linear 文档

        Args:
            project_id: 项目 ID
            title: 文档标题
            content: 文档内容（Markdown）
            icon: 图标 emoji
            color: 颜色（hex）

        Returns:
            Dict: 创建的文档信息，包含 id, slugId, url
        """
        mutation = """
        mutation CreateDocument($input: DocumentCreateInput!) {
          documentCreate(input: $input) {
            success
            document {
              id
              slugId
              title
              url
            }
          }
        }
        """

        input_data = {
            "projectId": project_id,
            "title": title,
            "content": content
        }

        if icon:
            input_data["icon"] = icon
        if color:
            input_data["color"] = color

        result = self.execute(mutation, {"input": input_data})

        if not result.get("documentCreate", {}).get("success"):
            raise Exception("创建文档失败")

        return result["documentCreate"]["document"]

    def update_issue(
        self,
        issue_id: str,
        **kwargs
    ) -> Dict:
        """
        更新 Issue

        Args:
            issue_id: Issue ID 或 identifier（如 LAN-123）
            **kwargs: 要更新的字段（parentId, title, description, priority, stateId, assigneeId 等）

        Returns:
            Dict: 更新后的 Issue 信息
        """
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue {
              id
              identifier
              title
              url
            }
          }
        }
        """

        result = self.execute(mutation, {
            "id": issue_id,
            "input": kwargs
        })

        if not result.get("issueUpdate", {}).get("success"):
            raise Exception(f"更新 Issue 失败: {issue_id}")

        return result["issueUpdate"]["issue"]


def main():
    """测试脚本"""
    client = LinearGraphQL()

    print("测试 Linear GraphQL API 连接...")

    # 测试获取团队
    teams = client.get_teams()
    print(f"\n✓ 找到 {len(teams)} 个团队:")
    for team in teams:
        print(f"  - {team['name']} ({team['key']})")

    # 测试获取用户
    users = client.get_users()
    print(f"\n✓ 找到 {len(users)} 个用户:")
    for user in users:
        print(f"  - {user.get('displayName') or user.get('name')} ({user.get('email')})")


if __name__ == "__main__":
    main()

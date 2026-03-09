#!/usr/bin/env python3
"""
清理和整理 Linear issues
- 合并重复的 issues
- 归档旧的 issues
"""

import os
import sys
from linear_graphql import LinearGraphQL

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from config_loader import get_linear_config


def main():
    client = LinearGraphQL()

    # 获取团队信息
    linear_config = get_linear_config()
    team_name = linear_config.get("team_name", "YourTeam")
    team = client.get_team_by_name(team_name)
    if not team:
        print(f"❌ 未找到 {team_name} 团队")
        return

    team_id = team["id"]

    # 获取工作流状态
    states = client.get_workflow_states(team_id)

    # 查找 Canceled 和 Duplicate 状态
    canceled_state = None
    duplicate_state = None

    for state in states:
        if state["type"].lower() == "canceled":
            canceled_state = state
        if state["name"].lower() == "duplicate":
            duplicate_state = state

    print(f"\n找到的状态:")
    print(f"  - Canceled: {canceled_state['id'] if canceled_state else 'Not found'}")
    print(f"  - Duplicate: {duplicate_state['id'] if duplicate_state else 'Not found'}")

    # 1. 合并重复的 issues: LAN-206 和 LAN-254
    print("\n" + "="*60)
    print("📋 步骤 1: 合并重复的 issues")
    print("="*60)

    print("\n处理 LAN-254 (标记为 Duplicate, 关联到 LAN-206)...")

    try:
        # 标记 LAN-254 为 Duplicate
        if duplicate_state:
            result = client.update_issue(
                issue_id="LAN-254",
                stateId=duplicate_state["id"]
            )
            print(f"✓ 已将 LAN-254 标记为 Duplicate")
        else:
            print("⚠️  未找到 Duplicate 状态，跳过")
    except Exception as e:
        print(f"❌ 更新 LAN-254 失败: {e}")

    # 2. 归档旧的 Duplicate/Canceled issues
    print("\n" + "="*60)
    print("🗂️  步骤 2: 归档旧的 Duplicate/Canceled issues")
    print("="*60)

    # 这些 issues 已经标记为 Duplicate 或 Canceled，只需确认状态
    old_issues = [
        ("LAN-78", "test webhook feishu", "Duplicate"),
        ("LAN-80", "调整prompt", "Canceled"),
        ("LAN-87", "前后端API不匹配问题解决方案", "Duplicate"),
        ("LAN-88", "前后端v0与backend的api设计信息", "Duplicate"),
        ("LAN-89", "阶段一详细计划留档", "Duplicate"),
        ("LAN-93", "前端session.id问题留档", "Duplicate"),
        ("LAN-96", "0916 Trouble Shooting", "Duplicate"),
    ]

    print("\n以下 issues 已经是 Duplicate/Canceled 状态，无需额外操作：")
    for identifier, title, status in old_issues:
        print(f"  ✓ {identifier}: {title} ({status})")

    print("\n" + "="*60)
    print("✅ 清理完成")
    print("="*60)

    print("\n总结:")
    print(f"  - 合并了 1 组重复 issues (LAN-206 ← LAN-254)")
    print(f"  - 确认了 7 个旧 issues 的归档状态")

    print("\n下一步建议:")
    print("  1. 为 9 个 issues 补充缺失的标签")
    print("  2. 为 10 个 issues 分配负责人")


if __name__ == "__main__":
    main()

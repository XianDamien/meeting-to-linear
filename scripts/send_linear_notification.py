#!/usr/bin/env python3
"""
发送 Linear Issues 通知邮件 - 增强版
支持从 Linear MCP 返回的 issue 对象直接生成并发送通知
"""

import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from send_email import MailSender
from config_loader import get_team_members, get_default_recipients


def _load_username_to_info():
    """从 config.json 加载用户名映射"""
    return get_team_members()


def _load_default_recipients():
    """从 config.json 加载默认收件人"""
    return get_default_recipients()


# 延迟加载（首次访问时从 config 读取）
USERNAME_TO_INFO = None
USERNAME_TO_EMAIL = None
DEFAULT_RECIPIENTS = None


def _ensure_loaded():
    """确保配置已加载"""
    global USERNAME_TO_INFO, USERNAME_TO_EMAIL, DEFAULT_RECIPIENTS
    if USERNAME_TO_INFO is None:
        USERNAME_TO_INFO = _load_username_to_info()
        USERNAME_TO_EMAIL = {k: v['email'] for k, v in USERNAME_TO_INFO.items()}
        DEFAULT_RECIPIENTS = _load_default_recipients()


def format_priority(priority_value):
    """将 Linear priority 值转换为显示文本"""
    priority_map = {
        1: 'P0 (Urgent)',
        2: 'P1 (High)',
        3: 'P2 (Medium)',
        4: 'P3 (Low)',
    }
    if isinstance(priority_value, dict):
        return f"P{priority_value.get('value', 0)} ({priority_value.get('name', 'Unknown')})"
    return priority_map.get(priority_value, f'P{priority_value}')


def extract_assignee_username(assignee_info):
    """从 Linear assignee 信息中提取用户名"""
    if isinstance(assignee_info, str):
        # 如果是字符串，可能是 email 或 username
        if '@' in assignee_info:
            # 从 email 提取用户名
            return assignee_info.split('@')[0]
        return assignee_info
    elif isinstance(assignee_info, dict):
        # 如果是字典，尝试获取不同的字段
        return assignee_info.get('name') or assignee_info.get('displayName') or assignee_info.get('email', '').split('@')[0]
    return str(assignee_info)


def format_assignee_display(assignee_username):
    """格式化负责人显示信息（包含真实姓名）"""
    _ensure_loaded()
    if assignee_username in USERNAME_TO_INFO:
        info = USERNAME_TO_INFO[assignee_username]
        return f"{info['name']} ({assignee_username})"
    return assignee_username


def get_priority_badge_class(priority_value):
    """获取优先级对应的 CSS 类名"""
    if isinstance(priority_value, dict):
        value = priority_value.get('value', 4)
    else:
        value = priority_value

    # Linear priority 值：1=Urgent, 2=High, 3=Medium, 4=Low
    priority_map = {
        1: 'priority-p1',
        2: 'priority-p2',
        3: 'priority-p3',
        4: 'priority-p4'
    }
    return priority_map.get(value, 'priority-p3')


def get_type_badge_class(labels):
    """根据 labels 获取 issue 类型的 CSS 类名"""
    if not labels:
        return 'type-feature'

    # labels 可能是字符串列表或字典列表
    label_names = []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                label_names.append(label.get('name', '').lower())
            else:
                label_names.append(str(label).lower())

    if 'bug' in label_names:
        return 'type-bug'
    elif 'tech debt' in label_names or 'techdebt' in label_names:
        return 'type-techdebt'
    else:
        return 'type-feature'


def generate_html_email(issues, meeting_date=None, meeting_topic=None, meeting_summary=None, video_url=None):
    """
    生成 Linear 风格的 HTML 邮件

    Args:
        issues: Linear issues 列表
        meeting_date: 会议日期
        meeting_topic: 会议主题
        meeting_summary: 会议摘要
        video_url: 会议录像 URL（可选）

    Returns:
        str: HTML 邮件内容
    """
    # 生成 issues HTML
    issues_html = ""
    for issue in issues:
        # 提取优先级
        priority = issue.get('priority', {})
        priority_text = format_priority(priority)
        priority_class = get_priority_badge_class(priority)

        # 提取负责人
        assignee = issue.get('assignee')
        assignee_username = extract_assignee_username(assignee) if assignee else '未分配'
        assignee_display = format_assignee_display(assignee_username)

        # 提取类型
        labels = issue.get('labels', [])
        type_class = get_type_badge_class(labels)

        # 确定类型文本
        if 'bug' in type_class:
            type_text = 'Bug'
        elif 'techdebt' in type_class:
            type_text = 'Tech Debt'
        else:
            type_text = 'Feature'

        issues_html += f'''
            <div class="issue">
                <div class="issue-header">
                    <span class="issue-id">{issue.get('identifier', 'N/A')}</span>
                    <div class="issue-title">
                        <a href="{issue.get('url', '#')}" target="_blank">{issue.get('title', '无标题')}</a>
                    </div>
                </div>
                <div class="issue-meta">
                    <span class="badge {priority_class}">{priority_text}</span>
                    <span class="badge {type_class}">{type_text}</span>
                    <span class="assignee">负责人: {assignee_display}</span>
                </div>
            </div>
        '''

    # 处理会议摘要（转换 Markdown 标题为 HTML）
    summary_html = ""
    if meeting_summary:
        # 简单的 Markdown 转 HTML
        lines = meeting_summary.split('\n')
        for line in lines:
            if line.startswith('## '):
                summary_html += f'<h2>{line[3:]}</h2>\n'
            elif line.startswith('### '):
                summary_html += f'<h3>{line[4:]}</h3>\n'
            elif line.startswith('- '):
                summary_html += f'<li>{line[2:]}</li>\n'
            elif line.strip():
                summary_html += f'<p>{line}</p>\n'
            else:
                summary_html += '<br>\n'

    # 构建完整的 HTML 邮件
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Linear Issues 通知</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "SF Pro Display", sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: #0d0d0d;
            background: #fafafa;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 720px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            padding: 48px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}

        h1 {{
            font-size: 28px;
            font-weight: 600;
            letter-spacing: -0.03em;
            margin-bottom: 6px;
            color: #0d0d0d;
        }}

        .date {{
            color: #6e6e80;
            font-size: 13px;
            margin-bottom: 40px;
        }}

        h2 {{
            font-size: 20px;
            font-weight: 600;
            margin: 48px 0 24px 0;
            letter-spacing: -0.02em;
            color: #0d0d0d;
        }}

        h2:first-of-type {{
            margin-top: 0;
        }}

        h3 {{
            font-size: 16px;
            font-weight: 600;
            margin: 32px 0 16px 0;
            letter-spacing: -0.01em;
            color: #0d0d0d;
        }}

        p {{
            margin-bottom: 16px;
            color: #27272a;
            line-height: 1.6;
        }}

        /* Linear Issues */
        .issues {{
            margin: 20px 0;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .issue {{
            background: #fafafa;
            border-radius: 8px;
            padding: 16px;
            border: 1px solid #f0f0f0;
            transition: all 0.15s ease;
        }}

        .issue:hover {{
            border-color: #e0e0e0;
            background: #f5f5f5;
        }}

        .issue-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}

        .issue-id {{
            font-family: 'SF Mono', 'Monaco', monospace;
            font-size: 12px;
            font-weight: 500;
            color: #6e6e80;
        }}

        .issue-title {{
            flex: 1;
        }}

        .issue-title a {{
            color: #0d0d0d;
            text-decoration: none;
            font-weight: 500;
            font-size: 14px;
        }}

        .issue-title a:hover {{
            color: #5E6AD2;
        }}

        .issue-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 500;
            letter-spacing: 0.01em;
        }}

        .priority-p1 {{
            background: #FEF2F2;
            color: #DC2626;
        }}

        .priority-p2 {{
            background: #FFF7ED;
            color: #EA580C;
        }}

        .priority-p3 {{
            background: #EEF2FF;
            color: #5E6AD2;
        }}

        .priority-p4 {{
            background: #F9FAFB;
            color: #6B7280;
        }}

        .type-feature {{
            background: #F3F4FF;
            color: #5E6AD2;
        }}

        .type-bug {{
            background: #FEF2F2;
            color: #DC2626;
        }}

        .type-techdebt {{
            background: #FFF7ED;
            color: #EA580C;
        }}

        .assignee {{
            color: #6e6e80;
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        /* Divider */
        hr {{
            border: none;
            border-top: 1px solid #f0f0f0;
            margin: 48px 0;
        }}

        ul, ol {{
            margin: 16px 0;
            padding-left: 24px;
        }}

        li {{
            margin: 6px 0;
            color: #27272a;
            line-height: 1.6;
        }}

        .note {{
            font-size: 12px;
            color: #6e6e80;
            background: #fafafa;
            padding: 12px 16px;
            border-radius: 8px;
            margin: 32px 0 0 0;
            border: 1px solid #f0f0f0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Linear Issues 通知</h1>
        <div class="date">{meeting_date or datetime.now().strftime('%Y-%m-%d')}</div>

        <h2>创建的 Linear Issues</h2>
        <p>根据 {meeting_date or "会议"} 讨论{f"（{meeting_topic}）" if meeting_topic else ""}，已创建以下 issues：</p>

        <div class="issues">
{issues_html}
        </div>

{f"""
        <hr>
        <h2>会议摘要</h2>
        {summary_html}
""" if meeting_summary else ""}

{f"""
        <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #f0f0f0;">
            <p><strong>📹 会议录像:</strong> <a href="{video_url}" target="_blank" style="color: #5E6AD2; text-decoration: none;">点击观看</a></p>
        </div>
""" if video_url else ""}

        <div class="note">
            本邮件通过 smtp.qq.com:465 发送，副本已保存至"已发送邮件"文件夹
        </div>
    </div>
</body>
</html>'''

    return html


def send_linear_issues_notification(
    issues,
    meeting_date=None,
    meeting_topic=None,
    meeting_summary=None,
    transcript_file_path=None,
    custom_recipients=None,
    video_url=None
):
    """
    发送 Linear issues 通知邮件

    Args:
        issues: Linear MCP 返回的 issue 对象列表，每个对象包含：
                - identifier: issue ID (如 LAN-227)
                - title: issue 标题
                - priority: 优先级对象或数值
                - assignee: 负责人信息（字符串或字典）
                - url: issue 链接
        meeting_date: 会议日期（可选，如 "2026-01-19"）
        meeting_topic: 会议主题（可选）
        meeting_summary: 会议摘要文本（可选）
        transcript_file_path: 会议转录文件路径（可选，将作为附件发送）
        custom_recipients: 自定义收件人列表（可选，如果不提供则使用默认团队成员列表）
        video_url: 会议录像 URL（可选）

    Returns:
        bool: 发送是否成功
    """
    if not issues:
        print("⚠ 没有 issues 需要发送通知")
        return False

    _ensure_loaded()

    # 使用自定义收件人或默认收件人
    recipients = custom_recipients if custom_recipients else DEFAULT_RECIPIENTS

    # 构建邮件主题
    subject_parts = []
    if meeting_date:
        subject_parts.append(f"{meeting_date} 会议")
    subject_parts.append(f"Linear Issues 通知 - {len(issues)} 个新建 Issues")
    if meeting_topic:
        subject_parts.append(f"({meeting_topic})")
    subject = " ".join(subject_parts)

    # 生成 HTML 邮件正文
    body = generate_html_email(
        issues=issues,
        meeting_date=meeting_date,
        meeting_topic=meeting_topic,
        meeting_summary=meeting_summary,
        video_url=video_url
    )

    # 准备附件列表
    attachments = []
    if transcript_file_path and os.path.exists(transcript_file_path):
        attachments.append(transcript_file_path)

    # 发送邮件
    print(f"\n📧 准备发送通知邮件...")
    print(f"   收件人: {', '.join(recipients)}")
    print(f"   Issues 数量: {len(issues)}")
    if attachments:
        print(f"   附件: {', '.join([os.path.basename(f) for f in attachments])}")

    sender = MailSender()
    success = sender.send_email(
        to_emails=recipients,
        subject=subject,
        body=body,
        is_html=True,
        attachments=attachments if attachments else None
    )

    return success


def main():
    """命令行使用示例"""
    import argparse

    parser = argparse.ArgumentParser(description='发送 Linear Issues 通知邮件')
    parser.add_argument('--issues-json', help='包含 issues 数据的 JSON 文件路径')
    parser.add_argument('--date', help='会议日期 (如 2026-01-19)')
    parser.add_argument('--topic', help='会议主题')
    parser.add_argument('--summary', help='会议摘要文本或文件路径')
    parser.add_argument('--transcript', help='会议转录文件路径（将作为附件发送）')
    parser.add_argument('--video-url', help='会议录像 URL')
    parser.add_argument('--to', action='append', help='自定义收件人（可多次指定或逗号分隔）')

    args = parser.parse_args()

    if args.issues_json:
        # 从 JSON 文件读取 issues
        try:
            with open(args.issues_json, 'r', encoding='utf-8') as f:
                issues = json.load(f)
        except FileNotFoundError:
            print(f"✗ 错误：找不到 JSON 文件: {args.issues_json}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"✗ 错误：JSON 格式无效: {e}")
            sys.exit(1)
    else:
        # 使用示例数据（仅用于测试）
        print("⚠️  警告：未提供 --issues-json 参数")
        print("   使用以下示例数据（仅用于测试，不适用于生产环境）\n")
        issues = [
            {
                'identifier': 'TEAM-001',
                'title': 'Example issue title',
                'priority': {'value': 3, 'name': 'Medium'},
                'assignee': 'user_a',
                'url': 'https://linear.app/your-team/issue/TEAM-001'
            },
            {
                'identifier': 'TEAM-002',
                'title': 'Another example issue',
                'priority': {'value': 2, 'name': 'High'},
                'assignee': 'user_b',
                'url': 'https://linear.app/your-team/issue/TEAM-002'
            }
        ]

    custom_recipients = None
    if args.to:
        # Flatten: support both --to a --to b and --to a,b
        custom_recipients = [
            email.strip() for entry in args.to
            for email in entry.split(',') if email.strip()
        ]

    # 读取会议摘要
    meeting_summary = None
    if args.summary:
        # 尝试作为文件路径读取
        if os.path.exists(args.summary):
            with open(args.summary, 'r', encoding='utf-8') as f:
                meeting_summary = f.read()
        else:
            # 作为文本内容
            meeting_summary = args.summary

    # 转录文件路径（不读取内容，作为附件）
    transcript_file_path = None
    if args.transcript and os.path.exists(args.transcript):
        transcript_file_path = args.transcript

    send_linear_issues_notification(
        issues=issues,
        meeting_date=args.date,
        meeting_topic=args.topic,
        meeting_summary=meeting_summary,
        transcript_file_path=transcript_file_path,
        custom_recipients=custom_recipients,
        video_url=args.video_url
    )


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
SMTP 邮件发送脚本
使用方法：
    python send_email.py --to "email1@example.com,email2@example.com" --subject "主题" --body "正文"
    或者作为模块导入使用

配置来源：config.json 中的 email 段
"""

import smtplib
import imaplib
import argparse
import time
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from typing import List

# 加载配置
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from config_loader import get_email_config


class MailSender:
    """邮件发送器（配置从 config.json 读取）"""

    def __init__(self, sender_email: str = None, auth_code: str = None, save_to_sent: bool = True):
        """
        初始化邮件发送器

        Args:
            sender_email: 发件人邮箱（如不提供，从 config.json 读取）
            auth_code: SMTP 授权码（如不提供，从 config.json 读取）
            save_to_sent: 是否将邮件副本保存到"已发送"文件夹
        """
        email_config = get_email_config()

        self.sender_email = sender_email or email_config.get("sender_email")
        self.auth_code = auth_code or email_config.get("auth_code")
        self.smtp_server = email_config.get("smtp_server", "smtp.qq.com")
        self.smtp_port = email_config.get("smtp_port", 465)
        self.imap_server = email_config.get("imap_server", "imap.qq.com")
        self.imap_port = email_config.get("imap_port", 993)
        self.save_to_sent = save_to_sent

        if not self.sender_email or not self.auth_code:
            raise ValueError(
                "邮件配置不完整！请在 config.json 的 email 段中配置 sender_email 和 auth_code"
            )

    def _save_to_sent_folder(self, message: MIMEMultipart) -> bool:
        """
        将邮件副本保存到"已发送"文件夹

        Args:
            message: 邮件对象

        Returns:
            bool: 保存是否成功
        """
        try:
            # 连接到IMAP服务器
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.sender_email, self.auth_code)

            # QQ邮箱的"已发送"文件夹名称是 "Sent Messages"
            mail.select('"Sent Messages"')

            # 将邮件添加到已发送文件夹
            mail.append(
                '"Sent Messages"',
                '\\Seen',  # 标记为已读
                imaplib.Time2Internaldate(time.time()),
                message.as_bytes()
            )

            mail.logout()
            print(f"✓ 邮件副本已保存到'已发送'文件夹")
            return True

        except Exception as e:
            print(f"⚠ 保存到'已发送'文件夹失败: {str(e)}")
            print(f"  (邮件已成功发送，但副本未保存)")
            return False

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        cc_emails: List[str] = None,
        is_html: bool = False,
        attachments: List[str] = None
    ) -> bool:
        """
        发送邮件

        Args:
            to_emails: 收件人邮箱列表
            subject: 邮件主题
            body: 邮件正文
            cc_emails: 抄送邮箱列表
            is_html: 是否为HTML格式
            attachments: 附件文件路径列表

        Returns:
            bool: 发送是否成功
        """
        try:
            # 创建邮件对象
            message = MIMEMultipart()
            message['From'] = self.sender_email
            message['To'] = ', '.join(to_emails)
            message['Subject'] = Header(subject, 'utf-8').encode()

            if cc_emails:
                message['Cc'] = ', '.join(cc_emails)

            # 添加邮件正文
            content_type = 'html' if is_html else 'plain'
            message.attach(MIMEText(body, content_type, 'utf-8'))

            # 添加附件
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)

                            filename = os.path.basename(file_path)
                            part.add_header(
                                'Content-Disposition',
                                'attachment',
                                filename=('utf-8', '', filename)
                            )
                            message.attach(part)
                            print(f"✓ 添加附件: {filename}")
                    else:
                        print(f"⚠ 附件不存在: {file_path}")

            # 连接SMTP服务器并发送
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender_email, self.auth_code)

                # 收件人列表
                recipients = to_emails + (cc_emails if cc_emails else [])
                server.sendmail(self.sender_email, recipients, message.as_string())

            print(f"✓ 邮件发送成功！")
            print(f"  收件人: {', '.join(to_emails)}")
            if cc_emails:
                print(f"  抄送: {', '.join(cc_emails)}")

            # 保存副本到"已发送"文件夹
            if self.save_to_sent:
                self._save_to_sent_folder(message)

            return True

        except Exception as e:
            print(f"✗ 邮件发送失败: {str(e)}")
            return False


# 向后兼容别名
QQMailSender = MailSender


def main():
    parser = argparse.ArgumentParser(description='发送邮件')
    parser.add_argument('--to', required=True, help='收件人邮箱，多个用逗号分隔')
    parser.add_argument('--subject', required=True, help='邮件主题')
    parser.add_argument('--body', required=True, help='邮件正文')
    parser.add_argument('--cc', help='抄送邮箱，多个用逗号分隔')
    parser.add_argument('--html', action='store_true', help='是否为HTML格式')
    parser.add_argument('--no-save-sent', action='store_true', help='不保存副本到已发送文件夹')

    args = parser.parse_args()

    # 解析收件人
    to_emails = [email.strip() for email in args.to.split(',')]
    cc_emails = [email.strip() for email in args.cc.split(',')] if args.cc else None

    # 创建发送器并发送
    sender = MailSender(save_to_sent=not args.no_save_sent)
    sender.send_email(
        to_emails=to_emails,
        subject=args.subject,
        body=args.body,
        cc_emails=cc_emails,
        is_html=args.html
    )


if __name__ == '__main__':
    main()

# 用户映射表

> 在 `config.json` 的 `team_members` 中配置，以下为示例。

## 团队成员

| 角色 | 姓名 | Linear 用户名 | 邮箱 |
|------|------|---------------|------|
| 产品经理 | User A | user_a | user_a@example.com |
| 前端开发 | User B | user_b | user_b@example.com |
| 后端开发 | User C | user_c | user_c@example.com |
| 项目经理 | User D | user_d | user_d@example.com |

## 固定收件人列表

**在 `config.json` 的 `default_recipients` 中配置。**

无论会议内容涉及谁，邮件发送给所有配置的收件人。

`--to` 参数不支持多次指定，必须对每个收件人**单独执行一次**发送命令。

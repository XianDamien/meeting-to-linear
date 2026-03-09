#!/usr/bin/env python3
"""
统一配置加载器
从 config.json 读取所有个性化配置
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 配置文件路径
SKILL_DIR = Path(__file__).parent
CONFIG_PATH = SKILL_DIR / "config.json"
CONFIG_EXAMPLE_PATH = SKILL_DIR / "config.example.json"


def load_config() -> Dict[str, Any]:
    """
    加载配置文件

    优先读取 config.json，不存在时报错并提示用户从 config.example.json 复制。

    Returns:
        Dict: 配置字典
    """
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    raise FileNotFoundError(
        f"\n{'=' * 60}\n"
        f"❌ 未找到配置文件 config.json！\n\n"
        f"请先复制并编辑配置：\n\n"
        f"  cp {CONFIG_EXAMPLE_PATH} {CONFIG_PATH}\n"
        f"  # 然后编辑 {CONFIG_PATH}，填入你的实际配置\n"
        f"{'=' * 60}"
    )


def get_linear_config() -> Dict[str, str]:
    """获取 Linear 配置"""
    config = load_config()
    return config.get("linear", {})


def get_email_config() -> Dict[str, Any]:
    """获取邮件配置"""
    config = load_config()
    return config.get("email", {})


def get_team_members() -> Dict[str, Dict[str, str]]:
    """获取团队成员映射"""
    config = load_config()
    return config.get("team_members", {})


def get_default_recipients() -> list:
    """获取默认收件人列表"""
    config = load_config()
    return config.get("default_recipients", [])


def get_oss_config() -> Dict[str, str]:
    """获取 OSS 配置"""
    config = load_config()
    return config.get("oss", {})


def get_asr_config() -> Dict[str, str]:
    """获取 ASR 配置"""
    config = load_config()
    return config.get("asr", {})

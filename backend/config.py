# -*- coding: utf-8 -*-
"""
数据库配置管理模块

支持从 .env 文件读取配置，兼容 SQLite 和 MySQL 双引擎。
配置项读取顺序：环境变量 > .env 文件 > 默认值
"""

import os
from typing import Dict, Any

# ──────────────────────── 尝试加载 .env 文件 ────────────────────────
try:
    from dotenv import load_dotenv

    # 从当前文件所在目录往上查找 .env
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=False)
    else:
        # 也尝试从项目根目录加载
        load_dotenv(override=False)
except ImportError:
    # python-dotenv 未安装，使用纯环境变量
    pass


# ──────────────────────── 默认配置 ────────────────────────
_DEFAULTS: Dict[str, Any] = {
    "DB_ENGINE": "sqlite",
    "SQLITE_PATH": "./data/app.db",
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": 3306,
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "",
    "MYSQL_DATABASE": "app_db",
    "MYSQL_CHARSET": "utf8mb4",
}


def _get_config(key: str) -> Any:
    """
    获取配置项，优先级：环境变量 > 默认值。

    Args:
        key: 配置项名称

    Returns:
        配置值，类型与默认值保持一致
    """
    raw = os.environ.get(key)
    if raw is None:
        return _DEFAULTS.get(key)
    # 根据默认值类型做类型转换
    default_val = _DEFAULTS.get(key)
    if isinstance(default_val, int):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return default_val
    return raw


# ──────────────────────── 对外暴露的配置属性 ────────────────────────

# 数据库引擎: "sqlite" 或 "mysql"
DB_ENGINE: str = str(_get_config("DB_ENGINE") or "sqlite")

# SQLite 数据库文件路径
SQLITE_PATH: str = str(_get_config("SQLITE_PATH") or "./data/app.db")

# MySQL 连接配置
MYSQL_HOST: str = str(_get_config("MYSQL_HOST") or "localhost")
MYSQL_PORT: int = int(_get_config("MYSQL_PORT") or 3306)
MYSQL_USER: str = str(_get_config("MYSQL_USER") or "root")
MYSQL_PASSWORD: str = str(_get_config("MYSQL_PASSWORD") or "")
MYSQL_DATABASE: str = str(_get_config("MYSQL_DATABASE") or "app_db")
MYSQL_CHARSET: str = str(_get_config("MYSQL_CHARSET") or "utf8mb4")


def get_db_config() -> Dict[str, Any]:
    """
    返回当前生效的全部数据库配置。

    Returns:
        dict: 包含所有配置项的字典
            - DB_ENGINE: 数据库引擎类型
            - SQLITE_PATH: SQLite 文件路径
            - MYSQL_HOST: MySQL 主机
            - MYSQL_PORT: MySQL 端口
            - MYSQL_USER: MySQL 用户名
            - MYSQL_PASSWORD: MySQL 密码
            - MYSQL_DATABASE: MySQL 数据库名
            - MYSQL_CHARSET: MySQL 字符集
    """
    return {
        "DB_ENGINE": DB_ENGINE,
        "SQLITE_PATH": SQLITE_PATH,
        "MYSQL_HOST": MYSQL_HOST,
        "MYSQL_PORT": MYSQL_PORT,
        "MYSQL_USER": MYSQL_USER,
        "MYSQL_PASSWORD": MYSQL_PASSWORD,
        "MYSQL_DATABASE": MYSQL_DATABASE,
        "MYSQL_CHARSET": MYSQL_CHARSET,
    }
# -*- coding: utf-8 -*-
"""
backend 包初始化模块

防护代码：禁止业务层直接在模块级别 import sqlite3 或 pymysql。
所有数据库访问必须通过 db_adapter 提供的 DatabaseAdapter 接口进行。
"""

import builtins

_original_import = builtins.__import__
_RESTRICTED_MODULES = {'sqlite3', 'pymysql'}
_ALLOWED_PREFIXES = {'db_adapter', 'test_adapter'}


def _is_caller_allowed() -> bool:
    """检查调用者是否在白名单中（允许直接导入 sqlite3/pymysql）"""
    import traceback
    stack = traceback.extract_stack()
    for frame_info in reversed(stack):
        for prefix in _ALLOWED_PREFIXES:
            if prefix in frame_info.filename:
                return True
    return False


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    """拦截业务层对 sqlite3/pymysql 的直接导入"""
    base_module = name.split('.')[0]
    if base_module in _RESTRICTED_MODULES:
        if not _is_caller_allowed():
            raise ImportError(
                "禁止业务层直接导入 '%s'。请使用 db_adapter.DatabaseAdapter 提供的抽象接口进行数据库操作。" % base_module
            )
    return _original_import(name, globals, locals, fromlist, level)


builtins.__import__ = _guarded_import
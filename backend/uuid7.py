# -*- coding: utf-8 -*-
"""
UUIDv7 生成器（Phase 2b）。

背景见 `docs/立项-存储层重构.md` §0.1：离线同步的硬阻塞是两台机器
各自 AUTOINCREMENT 会撞 id。主键必须全局唯一且可离线生成。

为什么选 v7 而不是 v4（RFC 9562）：
  * v7 前 48 位是 Unix 毫秒时间戳 → **时间有序**，字符串比较即时间比较。
    主键索引天然按时间聚集，新行总是追加到 B-Tree 末尾（页分裂少、写放大低）。
  * v4 完全随机 → 主键索引页随机写入，SQLite/MySQL/PG 都会频繁页分裂。
  * v7 仍保留 74 位随机熵（同毫秒内单调递增计数器 + 62 位随机），
    碰撞概率与 v4 同量级，可离线生成、无中心协调。

格式（36 字符标准连字符形式）：
  xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx
              ▲    ▲
              │    └── variant 位：10xx（8/9/a/b）
              └── version 位：0111（=7）

零第三方依赖：只用 `time` + `secrets` + `os.urandom` 回退。
"""

from __future__ import annotations

import secrets
import threading
import time

#: 上一次生成的时间戳毫秒（进程内单调性保证用）
_last_ms: int = 0
#: 同一毫秒内的 12 位计数器（0..0xFFF），保证同毫秒内严格递增
_last_rand_a: int = 0
_lock = threading.Lock()


def uuid7() -> str:
    """
    生成一个 UUIDv7 字符串（小写连字符形式）。

    线程安全，同毫秒内多次调用保证单调递增（计数器进位）。
    计数器 12 位用尽（同毫秒 > 4096 个）时自旋等待下一毫秒——
    单机实测每秒数万次以下不会触发，触发了也只是多等 <1ms。
    """
    global _last_ms, _last_rand_a
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms < _last_ms:
            # 时钟回拨：沿用上次时间戳，靠计数器继续递增，避免 id 回退
            ms = _last_ms
        if ms == _last_ms:
            _last_rand_a += 1
            if _last_rand_a > 0xFFF:
                # 同毫秒配额用尽：等到下一毫秒
                while ms <= _last_ms:
                    time.sleep(0.0005)
                    ms = time.time_ns() // 1_000_000
                _last_ms = ms
                _last_rand_a = secrets.randbits(12)
        else:
            _last_ms = ms
            _last_rand_a = secrets.randbits(12)

        rand_b = secrets.randbits(62)
        return _format(ms, _last_rand_a, rand_b)


def uuid7_hex() -> str:
    """无连字符的 32 字符形式（某些紧凑存储场景用）"""
    return uuid7().replace("-", "")


def _format(unix_ms: int, rand_a: int, rand_b: int) -> str:
    """按 RFC 9562 §5.7 组装 128 位：48 位时间 + 4 位版本 + 12 位 rand_a + 2 位 variant + 62 位 rand_b"""
    unix_ms &= 0xFFFFFFFFFFFF
    rand_a &= 0xFFF
    rand_b &= 0x3FFFFFFFFFFFFFFF
    hi = (unix_ms << 16) | (0x7 << 12) | rand_a
    lo = (0b10 << 62) | rand_b
    h = f"{hi:016x}{lo:016x}"
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def is_valid_uuid7(s: str) -> bool:
    """校验是否为合法 UUIDv7 字符串（版本位=7，变体位=8/9/a/b）"""
    if not isinstance(s, str) or len(s) != 36:
        return False
    parts = s.split("-")
    if [len(p) for p in parts] != [8, 4, 4, 4, 12]:
        return False
    try:
        compact = "".join(parts)
        int(compact, 16)
    except ValueError:
        return False
    # version 位：第 13 个十六进制字符必须为 7
    if compact[12] != "7":
        return False
    # variant 位：第 17 个十六进制字符必须为 8/9/a/b
    if compact[16] not in "89ab":
        return False
    return True


def uuid7_ms(u: str) -> int:
    """提取 UUIDv7 内嵌的 Unix 毫秒时间戳（便于调试与冲突排查）"""
    return int(u.replace("-", "")[0:12], 16)

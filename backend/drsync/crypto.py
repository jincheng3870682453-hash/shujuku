# -*- coding: utf-8 -*-
"""
drsync 加密包（.drsync 文件格式）。

格式（自定义头 + Fernet token）：
    offset 0   7B  magic   b'DRSYNC1'
    offset 7   1B  version 当前 = 1
    offset 8   16B salt    随机（os.urandom），每包不同
    offset 24  ..  token   cryptography Fernet 密文

密钥派生：PBKDF2HMAC(SHA256) 从口令派生，200_000 次迭代，32 字节后
urlsafe_base64 编码成 Fernet key。口令只在本机内存参与派生，
绝不写入包文件、绝不随网络传输（P2P 双方靠共同口令约定）。

口令错误 / 包损坏 / 魔数不对 统一抛 SyncError。
"""

from __future__ import annotations

import base64
import os
from typing import Union

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

#: 魔数：任何 .drsync 文件的前 7 字节
MAGIC = b"DRSYNC1"
#: 包格式版本
FORMAT_VERSION = 1

_SALT_SIZE = 16
_KDF_ITERATIONS = 200_000  # ≥ 200_000，OWASP 对 PBKDF2-SHA256 的推荐量级
_HEADER_SIZE = len(MAGIC) + 1 + _SALT_SIZE  # 7 + 1 + 16 = 24


class SyncError(Exception):
    """drsync 同步 / 加密包统一异常（口令错、包损坏、格式不对等）。"""


__all__ = ["SyncError", "MAGIC", "FORMAT_VERSION",
           "derive_key", "pack_bytes", "unpack_bytes", "write_drsync", "read_drsync"]


def derive_key(password: str, salt: bytes) -> bytes:
    """口令 + salt → Fernet key（urlsafe base64 的 32 字节）。"""
    if not password:
        raise SyncError("口令不能为空")
    if not isinstance(salt, (bytes, bytearray)) or len(salt) != _SALT_SIZE:
        raise SyncError(f"salt 必须是 {_SALT_SIZE} 字节")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=bytes(salt),
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def pack_bytes(plaintext: bytes, password: str) -> bytes:
    """明文字节 → 完整 .drsync 包字节（离开本函数即已是密文）。"""
    if not isinstance(plaintext, (bytes, bytearray)):
        raise SyncError("待加密内容必须是 bytes")
    salt = os.urandom(_SALT_SIZE)
    token = Fernet(derive_key(password, salt)).encrypt(bytes(plaintext))
    return MAGIC + bytes([FORMAT_VERSION]) + salt + token


def unpack_bytes(blob: bytes, password: str) -> bytes:
    """.drsync 包字节 → 明文字节；魔数/版本/口令任何一关不过都抛 SyncError。"""
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < _HEADER_SIZE + 1:
        raise SyncError("不是有效的 .drsync 包（长度不足）")
    blob = bytes(blob)
    if blob[: len(MAGIC)] != MAGIC:
        raise SyncError("magic 不匹配：这不是 .drsync 包")
    version = blob[len(MAGIC)]
    if version != FORMAT_VERSION:
        raise SyncError(f"不支持的 .drsync 包版本: {version}")
    salt = blob[len(MAGIC) + 1 : _HEADER_SIZE]
    token = blob[_HEADER_SIZE:]
    try:
        return Fernet(derive_key(password, salt)).decrypt(token)
    except InvalidToken:
        raise SyncError("解密失败：口令错误或包已损坏") from None


def write_drsync(path: str, plaintext_bytes: bytes, password: str) -> str:
    """加密并写入 .drsync 文件（落盘前即密文），返回文件路径。"""
    blob = pack_bytes(plaintext_bytes, password)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def read_drsync(path: str, password: str) -> bytes:
    """读取并解密 .drsync 文件，返回明文字节；口令错抛 SyncError。"""
    with open(path, "rb") as f:
        blob = f.read()
    return unpack_bytes(blob, password)

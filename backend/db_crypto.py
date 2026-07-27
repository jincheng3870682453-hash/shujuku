"""
数据库文件透明加密层
- 使用 AES-256-GCM 加密整个 SQLite 数据库文件
- 密钥派生：PBKDF2-HMAC-SHA256（10 万次迭代）
- 启动时解密到临时文件，操作期间透明读写，退出时加密回写
- 安全性：即使数据库文件被拷贝，没有密钥无法解密
"""

import os
import sys
import hashlib
import tempfile
import shutil
import atexit
from pathlib import Path
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ── 常量 ──
SALT_SIZE = 32          # 盐值长度
NONCE_SIZE = 12         # GCM nonce 长度
TAG_SIZE = 16           # GCM 认证标签长度
PBKDF2_ITERATIONS = 100_000  # PBKDF2 迭代次数
FILE_MAGIC = b"DREGENC\x01"  # 加密文件魔数 + 版本号


def _derive_key(password: str, salt: bytes) -> bytes:
    """从密码和盐值派生 256 位 AES 密钥"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def is_encrypted_file(filepath: str) -> bool:
    """检查文件是否为加密的数据库文件"""
    try:
        with open(filepath, "rb") as f:
            return f.read(len(FILE_MAGIC)) == FILE_MAGIC
    except (IOError, OSError):
        return False


def encrypt_file(source_path: str, dest_path: str, password: str) -> None:
    """
    加密数据库文件
    - 生成随机盐值和 nonce
    - PBKDF2 派生密钥
    - AES-256-GCM 加密
    - 写入加密文件（格式：MAGIC + salt + nonce + ciphertext）
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"源文件不存在: {source_path}")

    with open(source_path, "rb") as f:
        plaintext = f.read()

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(password, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(FILE_MAGIC)
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def decrypt_file(source_path: str, dest_path: str, password: str) -> None:
    """
    解密数据库文件
    - 从文件头读取 salt 和 nonce
    - PBKDF2 派生密钥
    - AES-256-GCM 解密并验证
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"加密文件不存在: {source_path}")

    with open(source_path, "rb") as f:
        magic = f.read(len(FILE_MAGIC))
        if magic != FILE_MAGIC:
            raise ValueError("不是有效的加密文件（魔数不匹配）")
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        ciphertext = f.read()

    if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE:
        raise ValueError("加密文件格式损坏")

    key = _derive_key(password, salt)

    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise ValueError(f"解密失败（密码错误或文件损坏）: {e}")

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(plaintext)


def change_password(
    filepath: str, old_password: str, new_password: str
) -> None:
    """修改加密密码（原地重新加密）"""
    if not is_encrypted_file(filepath):
        raise ValueError("目标文件不是加密文件")

    # 解密到临时内存
    plaintext_path = filepath + ".tmp.plain"
    try:
        decrypt_file(filepath, plaintext_path, old_password)
        encrypt_file(plaintext_path, filepath, new_password)
    finally:
        if os.path.exists(plaintext_path):
            os.remove(plaintext_path)


class EncryptedDatabase:
    """
    加密数据库管理器

    用法：
        db = EncryptedDatabase(
            encrypted_path="data/registry.db.enc",
            password="my-secret-key",
        )
        db.open()          # 解密到临时文件
        conn = db.connect()  # 获取 sqlite3 连接
        # ... 正常操作 ...
        db.close()         # 加密回写 + 清理临时文件

    也支持 with 语句：
        with EncryptedDatabase("data/registry.db.enc", "key") as db:
            conn = db.connect()
            ...
    """

    def __init__(self, encrypted_path: str, password: str):
        self.encrypted_path = os.path.abspath(encrypted_path)
        self.password = password
        self._temp_dir: Optional[str] = None
        self._temp_path: Optional[str] = None
        self._is_open = False

    def open(self) -> str:
        """打开加密数据库，返回临时明文文件路径"""
        if self._is_open:
            return self._temp_path

        self._temp_dir = tempfile.mkdtemp(prefix="dreg_db_")
        self._temp_path = os.path.join(self._temp_dir, "registry.db")

        if os.path.exists(self.encrypted_path):
            if is_encrypted_file(self.encrypted_path):
                decrypt_file(self.encrypted_path, self._temp_path, self.password)
            else:
                # 未加密文件：直接复制
                shutil.copy2(self.encrypted_path, self._temp_path)
        else:
            # 新数据库：创建空目录
            pass

        self._is_open = True

        # 注册退出时自动清理
        atexit.register(self._cleanup)
        return self._temp_path

    def connect(self):
        """返回 sqlite3 连接到临时明文数据库"""
        import sqlite3

        if not self._is_open:
            self.open()

        conn = sqlite3.connect(self._temp_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self) -> None:
        """保存：将临时文件加密写回"""
        if not self._is_open:
            return
        if self._temp_path and os.path.exists(self._temp_path):
            encrypt_file(self._temp_path, self.encrypted_path, self.password)

    def close(self) -> None:
        """关闭：加密回写 + 清理临时文件"""
        self.save()
        self._cleanup()
        self._is_open = False

    def _cleanup(self) -> None:
        """清理临时文件"""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def is_encrypted(self) -> bool:
        """当前加密文件是否已加密"""
        if os.path.exists(self.encrypted_path):
            return is_encrypted_file(self.encrypted_path)
        return False

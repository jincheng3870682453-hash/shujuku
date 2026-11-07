# -*- coding: utf-8 -*-
"""
drsync —— dynamic_registry 离线多机同步包（Phase 4）。

简洁 API：
    export_events(db_path, since=None)   导出变更事件流（水位增量 / 全量对账）
    import_events(db, events, source_node="")  按主键 upsert 导入，新者胜
    pack_bytes / unpack_bytes            明文 bytes <-> .drsync 包 bytes
    write_drsync / read_drsync           .drsync 文件读写（落盘即密文）
    SyncError                            口令错 / 包损坏统一异常

短别名（__init__ 暴露的便捷名）：
    export = export_events
    import_ = import_events   # `import` 是保留字，只能叫 import_
    pack = pack_bytes
    unpack = unpack_bytes

P2P 节点（可选增强，默认关闭）是懒加载的：
    from backend.drsync import node   # 只有这句才会连带引入 flask 相关代码
"""

from .crypto import (
    FORMAT_VERSION,
    MAGIC,
    SyncError,
    derive_key,
    pack_bytes,
    read_drsync,
    unpack_bytes,
    write_drsync,
)
from .events import SYNC_TABLES, compute_watermark, export_events, import_events

# 简洁别名
export = export_events
import_ = import_events  # noqa: A001  `import` 是保留字
pack = pack_bytes
unpack = unpack_bytes


def __getattr__(name):
    # node 懒加载：不 import node 就不引入 flask / socket 线程代码
    if name == "node":
        from . import node

        return node
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SYNC_TABLES",
    "export_events", "import_events", "compute_watermark",
    "pack_bytes", "unpack_bytes", "write_drsync", "read_drsync",
    "derive_key", "SyncError", "MAGIC", "FORMAT_VERSION",
    "export", "import_", "pack", "unpack",
]

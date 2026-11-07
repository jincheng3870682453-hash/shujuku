# -*- coding: utf-8 -*-
"""
vecsearch —— 本地轻量语义近似检索（字符 n-gram + TF-IDF 余弦）
================================================================

定位（docs/立项-存储层重构.md §0.1「本地轻量、后置实施」）：
HR 登记数据以结构化筛选为主，本模块提供**增强型**模糊/字形近似检索。
纯 Python 标准库实现：零第三方依赖、零网络调用，数据不出本机。

原理
----
* tokenize：中文按「单字 + 相邻二元组(bigram)」，英文/数字按小写词，
  标点与空白过滤（并切断 bigram 相邻关系）。
* 建索引：拼接指定字段 → tokenize → TF，存 {row_id: {token: tf}}；
  二遍累计 DF；IDF 取平滑式 idf(t) = log((N+1)/(df+1)) + 1；
  文档向量 w = tf * idf，模长（norm）预计算。
* 检索：query 同法向量化（忽略词表外 token），余弦相似度打分，
  按 min_score 阈值过滤 + top_k 降序返回，可附 ≤60 字原文片段（snippet）。

复杂度（纯 dict 运算，无 numpy）
--------------------------------
* build_index：O(总字符数) —— tokenize 线性扫描一遍，TF/DF/模长各一次线性累加。
* search：O(词表大小 × query token 数) —— 逐行对 query 的每个 token 做 O(1)
  dict 查找（全部文档 token 数之和即 postings 总量，与词表规模同阶）；
  1 万行 × 15 字段量级预期 <100ms（设计目标；纯 Python 实测以
  「1000 行建索引 <1s」烟测为准，见 backend/test_vecsearch.py，线性外推）。

局限（如实声明）
----------------
* 这是字符 n-gram 的**表面相似度，不是真语义**：同义改写检索不到
  （如「离职」搜不到「跳槽」），换真 embedding 模型的预留说明见 docs/vecsearch.md。
"""

from __future__ import annotations

import datetime
import json
import math
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

__all__ = [
    "VecSearchError", "tokenize", "build_index", "search",
    "persist_index", "load_index", "build_index_from_store", "get_row_text",
]

INDEX_VERSION = 1          # 索引格式版本；persist/load 据此校验
_SNIPPET_LEN = 60          # snippet 最大长度（字符）

# CJK 表意文字区：基本区 + 扩展A + 兼容区，覆盖中文姓名/地址/职位足够
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class VecSearchError(Exception):
    """vecsearch 模块错误（行结构不合法、索引版本不受支持等）。"""


# ──────────────────────────── 分词 ────────────────────────────

def tokenize(text: Any) -> List[str]:
    """
    中文友好分词：CJK 单字 + 相邻二元组；英文/数字按小写词；标点/空白过滤。

    复杂度 O(len(text))。全角字母/数字先 NFKC 归一化为半角再取词；
    非 CJK、非 ASCII 字母的字符（如西里尔文）按分隔符降级处理（如实声明）。
    """
    if text is None:
        return []
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize("NFKC", text)
    tokens: List[str] = []
    buf: List[str] = []              # 连续 ASCII 字母数字缓冲 → 一个词
    prev_cjk: Optional[str] = None   # 上一个连续 CJK 字符（中间未被分隔符打断）

    def _flush() -> None:
        if buf:
            tokens.append("".join(buf).lower())
            buf.clear()

    for ch in text:
        if _CJK_RE.match(ch):
            _flush()
            tokens.append(ch)            # 单字
            if prev_cjk is not None:
                tokens.append(prev_cjk + ch)  # 相邻 bigram
            prev_cjk = ch
        elif ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            prev_cjk = None
            buf.append(ch)
        elif "A" <= ch <= "Z":
            prev_cjk = None
            buf.append(ch.lower())
        else:
            # 标点/空白/其他符号：切断「相邻」关系
            _flush()
            prev_cjk = None
    _flush()
    return tokens


# ──────────────────────────── 建索引 ────────────────────────────

def _fingerprint(s: str) -> str:
    """稳定指纹（内置 hash 跨进程不稳定，这里用滚动混合，思路同 row_store.schema_version）。"""
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def _join_fields(row: Dict[str, Any], fields: Optional[List[str]]) -> str:
    """拼接指定字段值为一段文本；字段间以空格分隔，避免产生跨字段 bigram。"""
    keys = fields if fields else [k for k in row.keys() if k != "id"]
    parts: List[str] = []
    for k in keys:
        v = row.get(k)
        if v is None or v == "":
            continue
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (dict, list)):
            parts.append(json.dumps(v, ensure_ascii=False))
        elif isinstance(v, bool):
            parts.append("是" if v else "否")
        else:
            parts.append(str(v))
    return unicodedata.normalize("NFKC", " ".join(parts))


def _idf(df: Dict[str, int], n_docs: int, token: str) -> float:
    """平滑 IDF：log((N+1)/(df+1)) + 1；df 缺失按 0 计。"""
    return math.log((n_docs + 1) / (df.get(token, 0) + 1)) + 1.0


def _calc_norm(tf: Dict[str, int], df: Dict[str, int], n_docs: int) -> float:
    """文档向量模长：||tf * idf||，建索引时预计算（search 免去逐行开方）。"""
    s = 0.0
    for t, c in tf.items():
        w = c * _idf(df, n_docs, t)
        s += w * w
    return math.sqrt(s)


def build_index(rows: List[Dict[str, Any]],
                fields: Optional[List[str]] = None,
                keep_text: bool = True) -> Dict[str, Any]:
    """
    对 rows 建检索索引。

    参数
    ----
    rows      : [{"id": "<UUIDv7 字符串>", <字段>: <值>, ...}, ...]；缺 id 抛错。
    fields    : 参与检索的字段名；None 表示除 id 外的全部字段。
    keep_text : 是否保留每行拼接原文（供 search 生成 snippet；False 省内存）。

    返回纯 JSON 可序列化的 index dict：
      {version, fields, row_count, schema_fingerprint, built_at,
       tf: {row_id: {token: tf}}, df: {token: df},
       norms: {row_id: 模长}, texts: {row_id: 原文}|None}

    复杂度 O(总字符数)：tokenize 一遍 + TF/DF/模长各一次线性累加。
    """
    tf_by_row: Dict[str, Dict[str, int]] = {}
    texts: Dict[str, str] = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise VecSearchError(f"第 {i} 行不是 dict，无法建索引")
        if row.get("id") is None:
            raise VecSearchError(f"第 {i} 行缺少 id 字段")
        rid = str(row["id"])
        text = _join_fields(row, fields)
        tf: Dict[str, int] = {}
        for t in tokenize(text):
            tf[t] = tf.get(t, 0) + 1
        tf_by_row[rid] = tf          # 同 id 重复时以后出现者为准
        if keep_text:
            texts[rid] = text

    # DF 从最终 tf 表二遍累计：天然规避重复 row_id 导致的 DF 多计
    df: Dict[str, int] = {}
    for tf in tf_by_row.values():
        for t in tf:
            df[t] = df.get(t, 0) + 1
    n = len(tf_by_row)
    norms = {rid: _calc_norm(tf, df, n) for rid, tf in tf_by_row.items()}
    fp_src = "|".join(fields) if fields else "\x00all-fields"
    return {
        "version": INDEX_VERSION,
        "fields": list(fields) if fields else None,
        "row_count": n,
        "schema_fingerprint": _fingerprint(fp_src),
        "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tf": tf_by_row,
        "df": df,
        "norms": norms,
        "texts": texts if keep_text else None,
    }


# ──────────────────────────── 检索 ────────────────────────────

def _make_snippet(index: Dict[str, Any], rid: str, q_w: Dict[str, float]) -> str:
    """从原文中取首个命中的最稀有 token 所在片段，≤60 字。找不到原文/命中处返回 ""。"""
    text = (index.get("texts") or {}).get(rid)
    if not text:
        return ""
    df = index.get("df") or {}
    n = int(index.get("row_count") or 0)
    # 命中 token 里优先取 IDF 最高（最稀有）、其次最长的，避免 snippet 落在常见字上
    for t in sorted(q_w, key=lambda t: (_idf(df, n, t), len(t)), reverse=True):
        pos = text.lower().find(t.lower())
        if pos >= 0:
            start = max(0, pos - 20)
            end = min(len(text), start + _SNIPPET_LEN)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(text) else ""
            return prefix + text[start:end] + suffix
    return ""


def search(index: Dict[str, Any],
           query: str,
           top_k: int = 10,
           min_score: float = 0.05,
           snippet: bool = True) -> List[Dict[str, Any]]:
    """
    余弦相似度检索。返回 [{"row_id", "score", "snippet"?}]，score 降序、同分按 row_id 稳定排序。

    复杂度 O(词表大小 × query token 数)（见模块 docstring）。
    空 query / 空索引安全返回 []。词表外 token 忽略（OOV 只会等比压低所有分母）。
    索引被外力裁剪（norms/texts 缺某行 id）时现场兜底重算，不抛异常。

    参数：top_k 截断条数；min_score 相似度阈值；snippet=False 不取原文片段。
    """
    if not isinstance(index, dict) or index.get("version") != INDEX_VERSION:
        raise VecSearchError("索引缺失或版本不受支持，请重建索引")
    tf_map: Dict[str, Dict[str, int]] = index.get("tf") or {}
    df: Dict[str, int] = index.get("df") or {}
    n = int(index.get("row_count") or 0)
    q_tokens = tokenize(query)
    if not q_tokens or n == 0:
        return []

    q_tf: Dict[str, int] = {}
    for t in q_tokens:
        q_tf[t] = q_tf.get(t, 0) + 1
    q_w: Dict[str, float] = {}
    for t, c in q_tf.items():
        if t in df:  # 词表外 token 不参与打分
            q_w[t] = c * _idf(df, n, t)
    q_norm = math.sqrt(sum(w * w for w in q_w.values()))
    if not q_w or q_norm <= 0.0:
        return []

    norms = index.get("norms") or {}
    hits: List[Dict[str, Any]] = []
    for rid, tf in tf_map.items():
        dot = 0.0
        for t, qw in q_w.items():
            c = tf.get(t)
            if c:
                dot += qw * c * _idf(df, n, t)  # 文档权重 = tf * idf
        if dot <= 0.0:
            continue
        dnorm = norms.get(rid)
        if dnorm is None:  # 未知行 id（索引被裁剪）：兜底重算，保证安全
            dnorm = _calc_norm(tf, df, n)
        score = dot / (q_norm * dnorm) if dnorm > 0 else 0.0
        if score >= min_score:
            item: Dict[str, Any] = {"row_id": rid, "score": round(score, 6)}
            if snippet:
                snip = _make_snippet(index, rid, q_w)
                if snip:
                    item["snippet"] = snip
            hits.append(item)
    hits.sort(key=lambda h: (-h["score"], h["row_id"]))
    return hits[: max(0, int(top_k))]


def get_row_text(index: Dict[str, Any], row_id: str) -> Optional[str]:
    """取某行拼接原文；未知 row_id 安全返回 None（不抛异常）。"""
    return (index.get("texts") or {}).get(str(row_id))


# ──────────────────────────── 持久化 ────────────────────────────

def persist_index(index: Dict[str, Any], path: str) -> str:
    """索引落盘为 JSON（ensure_ascii=False）。元数据随 dict 一并保存：
    {schema_fingerprint, built_at, row_count, version:1}。返回文件路径。"""
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    return path


def load_index(path: str) -> Dict[str, Any]:
    """从磁盘加载索引；version 不为 1 时抛 VecSearchError（版本不兼容须重建）。"""
    with open(path, "r", encoding="utf-8") as f:
        index = json.load(f)
    if not isinstance(index, dict) or index.get("version") != INDEX_VERSION:
        raise VecSearchError(f"索引文件版本不受支持：{os.path.basename(path)}")
    return index


# ──────────────────────────── 顶层 API ────────────────────────────

def build_index_from_store(db: Any, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    从 backend.db_adapter 适配器直接建索引（不 import RowStore / app；
    遵循 fetch_rows 语义：自行 SELECT id, data 并 json.loads）。

    步骤：
      1) SELECT name, field_type FROM columns_meta ORDER BY position ASC
         （表不存在则降级：用每行 data 自带的字段）；
      2) SELECT id, data FROM rows_data，data 为 JSON 字符串，逐行 json.loads；
      3) fields=None 时取 columns_meta 全部字段名作为检索字段；
      4) schema_fingerprint 按「字段名:类型」聚合计算 —— schema 变更后
         可据此判定旧索引需重建。

    复杂度同 build_index：O(总字符数)。
    """
    cols: List[Dict[str, Any]] = []
    try:
        cols = db.fetch_all(
            "SELECT name, field_type FROM columns_meta ORDER BY position ASC"
        ) or []
    except Exception:
        cols = []  # 旧库/空库没有 columns_meta：安全降级

    if fields is None:
        fields = [c["name"] for c in cols] or None

    rows: List[Dict[str, Any]] = []
    for r in db.fetch_all("SELECT id, data FROM rows_data"):
        try:
            data = json.loads(r.get("data") or "{}")
        except (ValueError, TypeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        item = dict(data)
        item["id"] = r.get("id")
        rows.append(item)

    index = build_index(rows, fields=fields)
    if cols:
        src = "|".join(f"{c.get('name')}:{c.get('field_type')}" for c in cols)
    else:
        src = "|".join(fields) if fields else "all"
    index["schema_fingerprint"] = _fingerprint(src)
    return index

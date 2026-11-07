# vecsearch —— 本地轻量语义近似检索

## 是什么
`backend/vecsearch.py`：单文件、纯标准库的检索模块，用「字符 n-gram + TF-IDF 余弦」对
HR 登记数据做中文友好的模糊检索。中文按单字+相邻二元组分词，英文/数字按小写词；
零第三方依赖、零网络调用，数据不出本机（对应《立项-存储层重构》§0.1「本地轻量、后置实施」）。

## 为什么不用真 embedding
本机运行环境明确禁止安装任何第三方 ML 依赖（无 numpy / onnxruntime），也拉不起模型服务，
无法计算真实语义向量。字符 n-gram + TF-IDF 是该约束下合理的工程折衷：对中文姓名、
拼音混写、局部错字、子串命中（如「静宜」命中「陈静宜」）效果好，且内存/延迟可控
（1 万行 × 15 字段预期 <100ms，建索引 O(总字符数)）。

## 局限（如实声明）
- **非真语义**：同义改写检索不到——「离职」搜不到「跳槽」，「手机」搜不到「电话」。
- 依赖字符重叠，长查询词表外 token 被忽略，得分只反映表面相似度。
- 结构化精确筛选（部门=技术部）仍应走 SQL 列索引，本模块只做增强。

## API 一览
```python
from backend.vecsearch import (
    tokenize, build_index, search, persist_index, load_index,
    build_index_from_store, VecSearchError,
)

# 1) 从适配器直接建索引（自动读 columns_meta 全字段，自行 SELECT id, data）
index = build_index_from_store(db, fields=None)        # fields=None → 全部字段

# 2) 或对内存行建索引：rows = [{"id": "<uuid7>", "姓名": "陈静宜", ...}]
index = build_index(rows, fields=["姓名", "部门", "工号"])

# 3) 检索：返回 [{"row_id", "score", "snippet"}]，score 降序
hits = search(index, "静宜", top_k=10, min_score=0.05)

# 4) 持久化（JSON，ensure_ascii=False，metadata 含 version/schema_fingerprint）
persist_index(index, "data/vecsearch_index.json")
index = load_index("data/vecsearch_index.json")        # 版本不符抛 VecSearchError
```

## 如何换真模型（预留说明）
`search()` 只依赖 index dict 的 `{tf, df, norms, texts}` 结构；`build_index` 只依赖
`tokenize`。换真模型时：① 用本地 embedding 服务替换 `tokenize` 为向量产出，把 `tf/df/norms`
换成 `{row_id: vector}`（norms 同步为向量模长）；② `search` 内层点积换为向量点积；
③ persist 的 `version` 提升为 2，`load_index` 会拒绝旧索引并要求重建。接口签名无需变动。

## 索引维护
`schema_fingerprint` 按「字段名:类型」聚合，schema 变更后指纹变化即应重建索引；
每次数据批量写入后重跑 `build_index_from_store` 并 `persist_index` 即可，全量重建
对万行级数据是秒级以下操作，无需增量更新。

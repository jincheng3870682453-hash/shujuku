# drsync —— 离线多机同步指南（Phase 4）

`backend/drsync` 让桌面端在**无中心服务器**的前提下多机离线同步：
导出加密包始终可用（离线兜底），局域网 P2P 是自动化增强。
不开放公网端口、不引入任何云服务、口令不落盘不上网络。

## 一、三种用法

### 1. 手工加密包（永远可用，离线兜底）
```
python scripts/drsync_cli.py export --db data/app.db --out 同步包.drsync --password 口令
（U盘 / 网盘 / 微信文件传输助手，任选通道拷贝）
python scripts/drsync_cli.py import --db data/app.db --file 同步包.drsync --password 口令
```

### 2. 共享文件夹自动中继
把 export 的 `--out` 指向同步盘 / 共享目录（OneDrive、SMB 共享等），
各机器定时 import 该目录里最新的 .drsync 即可；包是密文，进网盘也安全。

### 3. LAN P2P（可选增强，默认关）
```
python scripts/drsync_cli.py serve --db data/app.db --password 口令   # 起节点
python scripts/drsync_cli.py peers                                   # 看邻居
```
每台机器都是对等节点：UDP 广播自动发现新机器，HTTP 只收加密包。
不执行 serve 就不开任何端口，自动退化为手工包模式。

## 二、同步语义
- 事件单元 = 整行 + updated_at/created_at + id；8 张表参与同步：
  users / columns_meta / rows_data / pending_changes / operations_log /
  audit_log / backups / ai_analysis_history（system_config 属本机配置，不同步）。
- 水位增量：每表按 updated_at（无则 created_at）> 上次水位导出；
  since 省略即全量对账。columns_meta 无时间戳列，按 max(id)（UUIDv7 时间有序）
  增量；`compute_watermark(事件)` 直接产出下次可用的每表水位 dict。
- 冲突：按主键 upsert，updated_at（无则 created_at）新者胜；
  rows_data.data 做字段级 union —— 两边新增的不同字段都保留，
  同字段冲突时以较新一行为准（行级时间戳无字段级历史）。
  A 改姓名 + B 改部门先后同步后，两人的修改都在。
- pending_changes 导入保持源库原 status；本地更新的审核状态不会被旧包覆盖。
- 导入整体在一个显式事务里，要么全进要么全不进；重复导入幂等。

## 三、安全模型
- .drsync = magic(`DRSYNC1`) + 版本 + 随机 16B salt + Fernet 密文；
  密钥 = PBKDF2HMAC-SHA256(口令, salt, 200_000 次迭代)。
- 口令只在本机内存参与派生：不写入包、不经网络传输、不落盘；
  双方靠共同口令约定，口令错抛 SyncError，包不入库。
- 收到的包必须先过 read_drsync 解密校验才进入 import，伪包 / 坏包直接拒绝。
- 不做 NAT 穿透、不连公网、无任何云服务；程序退出即无残留线程。

## 四、端口说明
| 端口 | 协议 | 用途 | 范围 |
| --- | --- | --- | --- |
| 41888 | UDP | beacon 广播发现（3s 周期，10s 超时剔除邻居） | 仅局域网 |
| 41889 | TCP | Flask 收包：POST /drsync/push、GET /drsync/peers | 默认绑 127.0.0.1；要接收局域网推包时绑所在网卡 |

beacon 包体：`{"magic":"DRBEACON1", node_id, hostname, http_port, ts}`。
端口被占用时节点自动降级为纯手工包模式，export / import 不受影响。

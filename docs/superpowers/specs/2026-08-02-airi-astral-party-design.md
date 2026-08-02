# airi_astral_party 设计规格

## 目标

`airi_astral_party` 为 AiriCore 提供《吉星派对》综合查询入口。系统由三个独立组件组成：AiriCore 内的 NoneBot 薄前端、独立运行的 Rust 后端，以及只负责 Unity 资源转换的 Python 工作器。

首版只支持国服 `CN`。QQ 用户可以绑定一个游戏 UID，查询自己的账号，也可以显式查询其他 UID 的合法公开数据。静态资料来自官方 GameData，实时玩家数据由后端内置的专用游戏账号通过长期 TCP 会话查询。结果优先使用客户端素材生成图片，失败时降级为中文结构化文本。

## 项目边界

### AiriCore 前端

前端位于：

`/Users/liko/Documents/GitHub/AiriCore/plugins/airi_astral_party`

前端只负责：

- 匹配 `astral` 命令。
- 从 OneBot 事件读取 QQ ID。
- 生成请求 UUID。
- 通过 HTTPS 调用后端统一命令接口。
- 校验响应 UUID、类型、数量和大小。
- 将裸 base64 图片补为 `base64://` 后发送。
- 图片发送失败时使用同一响应中的文本降级。

前端不得保存 QQ-UID 绑定、游戏资源、玩家缓存、游戏凭据或设备画像，也不得建立官服 TCP 连接、启动资源工作器或渲染业务图片。

### 独立 Rust 后端

后端是与 AiriCore 分离的相邻 Git 项目：

`/Users/liko/Documents/GitHub/airi_astral_party_server`

后端拥有独立配置、依赖、数据、日志、证书和生命周期。AiriCore 不启动、停止、重启或监控该进程。管理员使用后端自己的命令手动运行：

`astral-party-server serve`

后端负责：

- HTTPS API 与 Bearer 认证。
- `astral` 业务命令解析与分发。
- QQ-UID 绑定。
- GameData 静态查询。
- 专用账号认证档案与固定设备画像。
- 官服 TCP 长连接、心跳、推送和重连。
- 玩家实时查询、缓存、分页和权限边界。
- 资源版本发现、Python 工作器调度、验证和原子切换。
- 客户端素材图片渲染与文本降级。

独立后端不受 AiriCore 项目的代码风格、记忆、目录时间和测试临时文件规则约束。

### Python 资源工作器

Python 工作器属于独立后端项目，但使用已建立的 Conda 环境：

`/opt/homebrew/Caskroom/miniconda/base/envs/airi_astral_party`

工作器只在资源更新时由 Rust 后端启动，使用 UnityPy、protobuf、dnfile 和 dncil 完成以下工作：

- 解析 Unity Addressables catalog。
- 解包 GameData 和图片 AssetBundle。
- 从热更新 DLL 提取 Protobuf descriptor。
- 生成协议消息号映射。
- 将 GameData 转换为规范化 JSON。
- 生成逻辑资源键到素材文件的索引。

工作器不监听端口，不处理用户请求，不能读取后端 API token、专用账号认证档案、SQLite 或玩家缓存。

## 已确认范围

- 命令统一使用 `astral` 前缀。
- 首版只接受 `CN`，内部数据模型保留服务器字段。
- 一个 QQ 绑定一个游戏 UID。
- 提供玩家实时查询与静态资料查询。
- 查询用户只需提供 UID，不需要提交游戏凭据。
- 专用账号在 Rust 后端运行期间保持唯一长期登录会话。
- 专用账号必须与前期研究使用的个人账号不同。
- 请求官方服务时遵循已确认的原客户端报文格式、心跳和生命周期。
- 资源系统按照客户端版本发现、catalog 和按需 bundle 流程更新。
- 结果优先为图片，并通过 HTTPS 以 base64 返回前端。
- 不绕过服务端权限、硬件证明、反作弊或风控。

## 非目标

- 首版不支持 `CN` 以外的服务器。
- AiriCore 不直接访问后端数据目录或导入后端代码。
- AiriCore 不管理后端进程。
- 不提供修改玩家资料、领取奖励、好友操作或其他游戏写操作。
- 用户凭据上传与私有数据查询本轮只预留入口，不实现接收、解析或持久化。
- 不把真实 pcap、账号 token、设备画像或认证档案提交到任何 Git 仓库。

## 命令设计

### 账号管理

| 命令 | 行为 |
| --- | --- |
| `astral bind CN <UID>` | 验证 UID 后将当前 QQ 绑定到国服账号 |
| `astral bind` | 查看当前 QQ 的绑定状态 |
| `astral unbind` | 解除当前 QQ 的绑定 |

`CN` 大小写不敏感。其他服务器统一返回“当前仅支持国服 CN”。重复绑定覆盖旧绑定，并展示旧 UID 与新 UID。绑定必须先通过实时 UID 校验；后端未认证、官服不可用或 UID 不存在时，不修改已有绑定。

QQ ID 由前端从 OneBot 事件的 `user_id` 读取，后端以 `(platform, user_id)` 作为绑定主体。

### 用户凭据入口预留

保留 `astral auth upload` 作为未来私有数据查询入口。当前版本不接受参数、文件、token、二维码或截图，只返回“该功能尚未开放”。

未来用户凭据必须与专用账号完全隔离，以 QQ 和绑定 UID 明确归属，单独设计授权、撤销、替换、过期、会话和删除流程。本入口不改变当前普通 UID 查询只依赖专用账号的行为。

### 玩家查询

| 命令 | 行为 |
| --- | --- |
| `astral me` | 查询已绑定账号总览 |
| `astral me char [页码] [refresh]` | 查询服务端合法公开的角色数据 |
| `astral me skin [页码] [refresh]` | 查询服务端合法公开的皮肤数据 |
| `astral me record [页码] [refresh]` | 查询对局记录 |
| `astral me show [refresh]` | 查询公开展示信息 |
| `astral CN <UID>` | 查询指定 UID 的账号总览 |
| `astral CN <UID> char [页码] [refresh]` | 查询指定 UID 的公开角色数据 |
| `astral CN <UID> skin [页码] [refresh]` | 查询指定 UID 的公开皮肤数据 |
| `astral CN <UID> record [页码] [refresh]` | 查询指定 UID 的对局记录 |
| `astral CN <UID> show [refresh]` | 查询指定 UID 的公开展示信息 |

省略页码时使用第 1 页。页码必须是正整数，`refresh` 必须位于末尾。`me` 与显式 UID 最终进入同一查询服务，只在目标解析方式上不同。

角色和皮肤查询只呈现服务端合法返回或能够由公开战绩可靠推导的数据。服务端不公开完整仓库时，结果必须标注“公开可见”，不得把静态 GameData 的完整列表误报为玩家已拥有数据。

### 静态资料查询

| 命令 | 数据源 |
| --- | --- |
| `astral char <名称>` | `Character`、`STRCharacter` 与关联技能和素材 |
| `astral skill <名称>` | `Skill`、`STRSkill` |
| `astral card <名称>` | `Card`、`STRCard` |
| `astral item <名称>` | `Item`、`STRItem` |
| `astral map <名称>` | `Map` 与关联本地化数据 |
| `astral activity <名称>` | `Activity`、任务与奖励数据 |
| `astral search <关键词>` | 跨表名称与别名搜索 |

静态查询只访问后端当前 active 资源快照，不占用专用账号 TCP 会话。名称匹配依次尝试精确名称、规范化名称、别名和模糊候选。多条候选返回编号列表，不擅自选择对象。

## AiriCore 前端配置

`.env.prod` 新增以下键：

```dotenv
astral_backend_url = "https://127.0.0.1:8843"
astral_backend_token = ""
astral_backend_ca_file = ""
astral_backend_timeout = 30
```

- `astral_backend_url`：独立后端 HTTPS 根地址。
- `astral_backend_token`：前后端共享的随机高强度令牌。
- `astral_backend_ca_file`：自签名证书 CA 文件；留空使用系统信任库。
- `astral_backend_timeout`：统一命令请求总超时秒数。

修改 `.env.prod` 键集合时必须同步 `.env.prod_example`，保持相同分节和顺序。example 中 token 使用空字符串，CA 留空，地址使用安全本地占位值，每个键添加中文行内说明。

前端禁止使用 `verify=False`。证书无效、主机名不匹配或 CA 不受信任时拒绝连接，并向用户返回简短中文提示。

## HTTPS API

### 认证

所有业务接口使用：

`Authorization: Bearer <astral_backend_token>`

健康检查可不携带游戏数据，但 `/v1/status` 与 `/v1/command` 必须认证。token 不写入请求日志、异常详情或响应。

### 路由

- `GET /v1/health`：进程、API 版本和构建状态。
- `GET /v1/status`：资源版本、专用账号状态、代理路径和请求队列状态。
- `POST /v1/command`：统一业务入口。
- `POST /v1/admin/import-auth`：接收自动抓取工具提取的单个登录帧，使用独立管理员令牌。

### 命令请求

```json
{
  "request_id": "UUID",
  "platform": "qq",
  "user_id": "QQ号",
  "command": "astral me char 2"
}
```

前端不解析业务子命令，只验证消息确实以 `astral` 开头。后端负责完整语法、绑定和业务分发。

### 命令响应

```json
{
  "request_id": "UUID",
  "ok": true,
  "type": "image",
  "text": "文本降级内容",
  "images": ["裸base64内容"],
  "error_code": ""
}
```

`type` 只允许 `text` 或 `image`。图片响应必须同时包含可独立使用的 `text` 降级内容。后端不得返回本地路径、任意 URL、认证字段或内部异常栈。

前端校验响应 UUID 与请求一致、图片数量和解码后总大小不超过限制。前端对 `/v1/command` 不做自动业务重试；后端以 `request_id` 短期缓存结果，使人工重试和不确定网络结果保持幂等。

## Rust 后端技术架构

推荐使用：

- Axum：HTTPS API 路由。
- Tokio：异步运行时、TCP、任务和优雅关闭。
- Rustls：TLS，不依赖 OpenSSL。
- Reqwest：HTTP/CDN 请求。
- Serde：配置、API 和规范化数据。
- Prost 与 prost-reflect：动态 Protobuf descriptor 和消息。
- Rusqlite：SQLite、事务和迁移。
- Image、imageproc 与 ab_glyph：图片渲染。
- Tracing：结构化脱敏日志。
- XChaCha20-Poly1305：认证档案加密。

模块边界：

```text
src/
├── api/          HTTPS、Bearer 认证、限流和响应模型
├── command/      astral 语法、目标解析和分发
├── binding/      QQ-UID 绑定服务
├── auth/         认证档案、设备哈希和导入 CLI
├── protocol/     descriptor、帧头、代理、TCP 会话和心跳
├── player/       RPC、规范化玩家模型、缓存和分页
├── resources/    版本发现、工作器、验证、active 与 previous
├── static_data/  GameData 索引、关联和搜索
├── render/       视图模型、素材加载、模板和 base64
├── storage/      SQLite、迁移和事务
├── config.rs     后端独立配置
├── lib.rs        组件装配与可测试入口
└── main.rs       serve、import-auth 和优雅关闭
```

每个模块只通过公开数据模型或 trait 通信。API 不直接访问 SQLite，命令解析器不直接访问网络，渲染器不读取 Protobuf 或认证档案。

## 后端目录与配置

```text
airi_astral_party_server/
├── src/
├── worker/
├── tests/
├── data/
│   ├── auth/
│   ├── cache/
│   └── resources/
├── logs/
├── certificates/
├── .env.prod
├── .env.prod_example
├── Cargo.toml
└── README.md
```

后端 `.env.prod` 至少配置：监听地址、监听端口、API token、TLS 证书、TLS 私钥、认证档案主密钥、SQLite 路径、数据目录、资源工作器 Python、HTTP 代理和 TCP SOCKS5 代理。

正式数据、日志、`.env.prod`、TLS 私钥和认证档案不进入 Git。重要数据只保存在后端 `data/`，不依赖系统临时目录。

## 已确认的官方协议基础

### HTTP 与 CDN

当前国服客户端版本为 `3.2.0`，平台路由为 `CN_ANDROID`。已确认：

- 登录图：`GET http://se-web-cn.feimogames.com:7878/api/loginImage/get?route=CN_ANDROID&version=<version>`
- 资源版本：`GET http://se-web-cn.feimogames.com:7878/api/hotaddressExtend/get?route=CN_ANDROID&version=<version>`
- catalog：`<sourceUrl>/catalog_<version>.hash` 与 `<sourceUrl>/catalog_<version>.json`

后端不得写死当前 CDN 构建号，必须从版本接口获取 `sourceUrl`。

### Addressables 与 GameData

当前 catalog 已确认包含约 1.3 万个 key 和约 6000 个 bundle internal ID。`GameData_CN` 包含 153 张 Protobuf 表，包括角色、技能、卡牌、物品、皮肤、地图、活动、任务、遗物和怪物。

热更新 DLL 中已恢复 160 个 descriptor，当前协议映射包含 455 个消息号。现有研究资料只用于实现和脱敏测试，不包含个人账号原始认证抓包。

### TCP

当前国服地址为 `101.132.186.71:8800`。协议为 TCP + Protobuf，固定 35 字节帧头：

- offset 0：4 字节大端 body 长度。
- offset 12：2 字节大端消息号。
- offset 24：4 字节小端序列号。
- offset 35：Protobuf body 起点。

已确认消息：

- `5001/5002`：`ConnectC2S` / `ConnectS2C`
- `5003/5004`：`HeartbeatC2S` / `HeartbeatS2C`
- `5263/5264`：`GetPlayerSimpleC2S` / `GetPlayerSimpleS2C`
- `5185/5186`：`SearchPlayerC2S` / `SearchPlayerS2C`
- `5153/5154`：`GetShowPlayerC2S` / `GetShowPlayerS2C`
- `5155/5156`：`GetPlayerFightRecordC2S` / `GetPlayerFightRecordS2C`

心跳间隔为 10 秒。实际功能必须在专用账号认证后验证请求字段、权限和响应语义，不能只依赖消息名称推断。

## 专用账号认证档案

### 采集

认证适配阶段由用户在官方客户端登录新建的专用账号。抓包时同时采集 `ConnectC2S` 所需凭据和该请求实际携带的设备、安装字段。前期个人账号的 token 和设备信息不得复用。

使用 Rust CLI 导入：

`astral-party-server import-auth <pcap>`

导入器只解析首个合法 `ConnectC2S`。成功写入认证档案后提示管理员删除原始 pcap，后端不复制或归档抓包。

后端同时提供独立的自动同步工具。工具通过配置的 ADB 路径连接 `127.0.0.1:5555`，只抓取目标应用产生的 8800/TCP 流量，检测到首个完整 `ConnectC2S` 后立即停止。工具在本机临时工作目录解析出登录帧和不可变帧头模板，通过证书校验的 HTTPS 调用 `/v1/admin/import-auth`，成功后删除原始 pcap。同步接口使用与 AiriCore 业务 token 不同的管理员 token，限制请求体大小，只接受一个登录帧，并沿用设备哈希一致性校验；设备不一致时拒绝同步，不允许远程重置设备身份。

### 固定设备画像

认证档案分为可通过正常登录更新的凭据区与不可自动变化的设备区。设备区保存协议实际使用的设备标识、安装标识、Android 版本、机型、语言和时区；应用版本、资源版本和国服路由属于可更新协议状态。

设备区计算独立哈希。导入新凭据、后端重启、TCP 重连、资源更新或普通认证失败均不得改变设备区。新抓包设备哈希不一致时拒绝导入，只有管理员显式执行设备重置流程后才允许建立新档案。

### 加密与恢复

认证档案使用 XChaCha20-Poly1305 加密，主密钥只存在后端 `.env.prod`。主档案和备份使用同目录原子替换与文件权限限制。

主副本均损坏、校验失败或无法解密时，实时查询进入 `AUTH_REQUIRED`，不得自动生成设备身份或认证字段。认证数据、完整 `ConnectC2S`、设备标识和 token 不进入 SQLite、普通日志或 API 响应。

## 会话生命周期

状态机：

`AUTH_REQUIRED -> CONNECTING -> ONLINE -> BACKOFF`

后端启动时加载资源和认证档案，然后建立唯一国服会话。进入 `ONLINE` 后每 10 秒发送心跳，持续读取服务端推送。所有玩家 RPC 经一个有界队列进入同一会话，不为单个查询重复登录。

普通网络故障采用带抖动的指数退避。认证失效、账号被顶下线或服务端明确拒绝时返回 `AUTH_REQUIRED`，停止密集重试。后端正常关闭时停止接收新业务请求、完成可结束的在途请求、停止心跳并关闭连接。

每个 RPC 以序列号关联等待结果。超时后清理关联项；迟到响应不得匹配后续请求。未知消息和无关推送只记录脱敏消息号与长度。

## 代理策略

后端 HTTP、catalog 和 CDN 请求使用 `127.0.0.1:7890` HTTP 或 mixed 代理。游戏 TCP 使用同端口的 SOCKS5 能力；若代理不支持 SOCKS5，后端必须在启动状态中明确显示 TCP 直连或拒绝启动，不能静默改变路径。

AiriCore 到独立后端的 HTTPS 通信不经过游戏代理配置。

## 资源维护

### 存储

```text
data/resources/
├── versions/
├── staging/
├── cache/
├── active
└── previous
```

catalog、GameData、descriptor、协议映射和核心渲染素材主动镜像，其他大图按查询需要懒加载。系统临时目录不保存唯一副本。

### 更新流程

1. 后端启动时检查一次版本，之后默认每 6 小时检查。
2. Rust 下载版本信息、catalog 和目标 bundle 到 staging。
3. Rust 生成只包含资源路径、版本和任务类型的工作清单。
4. Rust 启动一次性 Python 工作器。
5. 工作器输出 GameData JSON、descriptor、协议映射和素材索引。
6. Rust 验证 hash、bundle、必需表、消息映射和核心素材。
7. 验证成功后事务记录版本并原子切换 active，旧 active 成为 previous。
8. 失败时保留旧 active，清理不完整 staging 并记录脱敏错误。

单个查询始终固定使用一个资源快照，不能混合新旧 GameData 和图片。只清理既非 active、也非 previous 的旧版本和可重新下载缓存。

## SQLite 与缓存

SQLite 开启 WAL、busy timeout、外键和迁移，包含：

- `bindings`：平台、用户 ID、服务器、UID 和更新时间。
- `player_cache`：查询键、规范化数据、采集时间、过期时间和资源版本。
- `resource_versions`：版本、hash、状态和激活时间。
- `request_cache`：短期请求 UUID 与完整响应，用于幂等。
- `schema_migrations`：迁移版本。

认证档案不进入 SQLite。

玩家缓存键为 `(server, uid, feature, normalized_args)`：

- 总览、角色、皮肤和展示：5 分钟。
- 战绩：1 分钟。
- 静态数据：随 active 资源版本失效。

`refresh` 绕过普通读取 TTL，但仍受单 UID 最短刷新间隔、队列上限和官服请求限速。官服暂时不可用时可返回最近成功数据，并标注“缓存数据”和采集时间。

## 图片渲染

Rust 后端为总览、角色、皮肤、战绩、展示和静态资料建立独立模板。模板只接收规范化视图模型，不读取 TCP 报文、SQLite 行或认证档案。

- 背景、立绘、头像、图标和稀有度优先使用 active 客户端素材。
- 长列表自动分页，显示页码、UID、服务器和采集时间。
- 服务端只公开部分数据时显示“公开可见”。
- 单个素材缺失时使用统一占位元素，不让整张图片失败。
- 后端返回裸 base64 与完整文本降级，不返回本地路径。
- 前端只负责补 `base64://` 并发送。

图片发送失败时，前端使用同一后端响应的 `text`，不得再次请求官服或后端。

## 启动与故障边界

后端启动顺序：

1. 加载独立配置。
2. 验证 TLS、API token、认证主密钥和数据目录。
3. 执行 SQLite 迁移。
4. 加载 active 资源快照。
5. 启动 HTTPS API。
6. 加载认证档案并连接官服。
7. 启动资源检查和缓存维护任务。

即使专用账号尚未认证，HTTPS 健康检查和静态资料仍可服务。AiriCore 停止或重启不影响后端会话。后端崩溃后只能由管理员手动重启。

AiriCore 前端只区分：后端不可达、TLS 失败、401、超时、后端繁忙和业务错误。前端不读取后端日志，也不根据错误自动更改 URL、CA 或 token。

## 安全与日志

- HTTPS 必须验证证书和主机名。
- Bearer token 使用常量时间比较，并从所有日志字段中排除。
- 认证同步接口使用独立管理员 token，AiriCore 前端永远不持有该 token。
- API 限制请求体、命令长度、图片数量和响应总大小。
- 后端只接受合法 UUID、平台、用户 ID 和 `astral` 命令。
- 用户输入不拼接到 shell；Python 工作器使用固定程序和参数数组启动。
- 日志可记录 request ID、QQ ID、UID、功能、耗时、缓存命中、消息号和资源版本。
- 日志不得记录 token、认证档案、设备标识、完整登录报文或未来用户凭据。
- 服务端返回非公开、无权限或空数据时如实展示，不尝试隐藏或管理接口。

## 验证方案

### Rust 单元测试

- 命令语法、CN 限制、页码和 `refresh`。
- 35 字节帧头、消息号、序列号和拆包粘包。
- 设备区哈希、加密档案、备份恢复和拒绝静默重建。
- 缓存 TTL、单 UID 冷却、请求幂等和绑定覆盖事务。

### Rust 集成测试

- 临时 SQLite 迁移、WAL 和事务回滚。
- 测试 CA 下的 HTTPS、Bearer 认证、请求大小限制和响应模型。
- 假 TCP 官服下的登录、心跳、推送、RPC、超时、迟到响应和重连。
- 资源工作器成功激活、失败回滚和查询快照隔离。
- 图片空数据、单页、多页、素材缺失和文本降级。

### Python 工作器测试

- catalog 解码与逻辑 key 映射。
- GameData 153 表解码与必需表检查。
- 热更新 DLL descriptor 与协议映射提取。
- 素材导出、工作清单限制和禁止读取后端敏感文件。

### AiriCore 前端测试

- 后端离线、TLS 错误、401、超时和畸形 JSON。
- request ID 不一致、未知类型、超量图片和非法 base64。
- 文本、单图、多图、图片发送失败后的文本降级。
- `.env.prod` 与 `.env.prod_example` 键和顺序一致。

### 官服集成

用户登录专用账号后采集新 pcap，导入凭据与设备画像。使用少量指定 UID 验证登录、心跳、总览、展示、角色、皮肤和战绩的真实公开范围。只有响应字段语义确认的功能才能启用。

## 验收标准

- Rust 后端可以在 AiriCore 未运行时独立启动并维持专用账号会话。
- AiriCore 不导入、启动或直接访问后端内部资源。
- 前后端通过证书验证的 HTTPS 与 Bearer token 通信。
- `astral bind CN <UID>`、`astral me` 和显式 UID 查询由后端统一处理。
- 非 CN 输入不会触发官服查询。
- 静态查询不占用专用账号会话。
- Python 工作器只能访问资源任务目录，不能访问认证和玩家数据。
- 资源更新具有 staging 验证、原子 active 切换和 previous 回滚。
- 专用账号凭据和固定设备画像由同一次官方登录抓包采集并加密保存。
- 设备区在重启、重连、资源更新和凭据刷新中保持不变。
- 后端图片通过 base64 返回，AiriCore 图片失败时使用同一响应文本降级。
- 两个仓库和普通日志中均不存在真实凭据、设备画像或原始 pcap。

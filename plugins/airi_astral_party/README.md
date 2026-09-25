# 吉星派对查询

通过国服客户端的 TCP / Protobuf 协议查询玩家公开资料，以游戏内 UI 切图、角色图示和字体合成图片。

## 指令

| 指令 | 用途 |
|---|---|
| `astral help` | 图片帮助；单独发送 `astral` 也显示帮助 |
| `astral bind UID` | 设置自己的默认查询玩家，仅为查询偏好 |
| `astral unbind` | 删除默认查询玩家 |
| `astral me` | 已绑定玩家的昵称、等级、点赞数及公开生涯统计 |
| `astral UID` | 指定玩家的公开资料，无需绑定 |
| `astral me recent` | 已绑定玩家的最近对局，每页六场；默认第一页 |
| `astral me recent 页码` | 已绑定玩家指定页的战绩 |
| `astral UID recent` | 指定玩家的最近对局，也可追加页码 |
| `astral me battle 序号` | 已绑定玩家的某一场对局 |
| `astral UID battle 序号` | 指定玩家的某一场对局 |
| `astral status` | 配置与绑定状态 |

所有指令均以 `astral` 开头，参数间使用空格；不再注册原中文指令。指令前缀遵循 Airi 的 `COMMAND_START` 配置。`me` 及其 `recent`、`battle` 子指令仅在已绑定时可用；UID、页码和序号应替换为实际数字。绑定不验证账号所有权。对局序号按照查询时的最新战绩从新到旧排列，新对局产生后序号可能改变。

## 配置专用查询账号

1. 在 AiriCore 工作目录执行 `conda run -n airidev python -m pip install -r requirements.txt`，新增依赖为 `protobuf==6.33.6`。
2. 在官方客户端自行注册或选择专用国服账号，登录并进入游戏大厅。
3. 运行下方本机配置工具，按提示从此次游戏日志提取 SDK 参数，并生成 `data/astral_party/config.json`。保持大厅打开直到保存完成，然后正常关闭游戏。
4. 启动或重启 Airi，发送 `astral status`，再用一个已知 UID 验证资料、战绩与单场详情。

### 本机账号配置工具

在 AiriCore 目录运行：

```powershell
conda run --no-capture-output -n airidev python plugins/airi_astral_party/account_tool.py
```

工具用于获取你已登录的专用账号的查询凭据，不自动注册游戏账号。默认导出模式读取当前用户的 `AppData/LocalLow/feimo/吉星派对/Player.log`，从游戏原有日志提取最新登录的游戏、渠道、应用、设备标识及 `sid`、`extra`，再从 `吉星派对.exe` 的已建立 TCP 连接识别服务器。导出模式不联网；`--login` 和 `--refresh` 会连接官方授权服务。工具不启动 Bot。开发测试只使用合成数据，实际授权仍需首次运行验证。

终端仅显示脱敏摘要，不显示会话与设备标识。确认后原子写入配置；更新已有配置会保留 `timeout` 和 `cooldown`，坏档不覆盖。Windows 文件权限限制为当前用户与系统；其他系统使用 `0600`。未修改的游戏日志本身由官方客户端管理。

常用参数：

| 参数 | 用途 |
|---|---|
| `--log-file 路径` | 指定本次专用账号登录的 UTF-8 日志；读取末尾最多 16 MiB |
| `--host 地址` | 无法自动识别时，手动指定游戏 TCP 服务器地址 |
| `--port 8800` | 指定实际游戏端口，默认 8800 |
| `--pid 进程号` | 限定用于识别服务器的游戏进程 |
| `--client-version 3.2.1` | 指定客户端应用版本，与实际安装版本一致 |
| `--output 路径` | 指定配置输出位置，默认指向该仓库的 `data/astral_party/config.json` |
| `--yes` | 已登录正确的专用账号，跳过交互确认并写入或更新配置 |
| `--dry-run` | 只检查并显示脱敏摘要，不写入配置 |
| `--login` | 使用已有服务器配置，私密输入飞魔账号手机号和密码；需要联网 |
| `--refresh` | 读取飞魔自动登录凭据，达到六小时间隔后重新登录并获取游戏 sid；需要联网 |
| `--check` | 离线检查已有配置与续期状态，不读取游戏日志或访问网络 |
| `--sdk-channel 标识` | 仅用于飞魔登录：飞魔安装渠道，对应游戏目录或上级目录 `SetupInfo.ini` 的 `[Setup] fileName`，没有该文件时使用客户端默认值 `test_junhai`；不同于 `channel_id` |

只检查本次登录参数：

```powershell
conda run --no-capture-output -n airidev python plugins/airi_astral_party/account_tool.py --yes --dry-run
```

找不到完整登录记录时，重新启动官方客户端，用专用账号登录进入大厅后重试；请勿在提取前点击“注销账号”。日志中最后一次登录已退出、失败或重新初始化时，工具不会退回使用更早的凭据。工具不会改变日志，也不会替你切换账号；读取的账号以你在官方客户端实际登录的账号为准。

也可将 `config.example.json` 复制为 `data/astral_party/config.json`，按下表手动填写。

| 配置字段 | 说明 |
|---|---|
| `host`、`port` | 游戏 TCP 服务器地址与端口；必填地址，不是官网、CDN 或 TapTap 网页地址 |
| `client_version` | 客户端应用版本，当前解析安装包为 `3.2.1`；热更新资源版本与此值不同 |
| `game_id`、`channel_id`、`app_id` | 官方 SDK 登录回调对应的三项标识，均必填 |
| `sid` | 专用账号当前有效的 SDK 会话凭据，必填；不会通过聊天接收 |
| `extra` | 官方 SDK 回调附加参数，若无则留空 |
| `device_id` | 对应登录会话的设备标识，必填 |
| `timeout` | 每次连接/请求超时秒数，默认 15，上限 30 |
| `cooldown` | 全插件查询间隔秒数，默认 10 |

这些参数对应官方客户端 `LoginServiceHelper.RequestConnectWithBnSdk(gameID, channelID, appID, sid, extra, deviceid)`。需由专用账号的授权登录流程取得，不能拿玩家 UID、TapTap 网页 Cookie 或平台 access_token 直接替代 `sid`。`renewal` 是工具生成的可选续期材料，禁止手动填入网页 Cookie。只完成默认导出时仍是临时会话；重新导出会清除旧续期材料，防止更换账号后旧授权覆盖新账号。下一次查询自动重读配置。服务器地址对应当前渠道官方引导返回的 `serverUrl`；安装包中的引导路径为 `/api/hotaddressServer/get?route=CN_TAPTAP&version=...`，服务地址/版本以实际客户端为准。

### 飞魔账号与 Linux 持续运行

自动登录只使用飞魔账号的手机号和密码，对应客户端 `TYPE_TELPWD=19`、`tel_num` / `password`。不使用 TapTap 扫码、Cookie 或令牌。请先在官方客户端完成专用飞魔账号的注册、设置密码和必要验证；本工具不会注册账号。

实现依据本机 3.2.1 客户端中的飞魔 SDK 静态还原，已通过离线测试，尚未使用真实专用账号验证。六小时是工具的刷新间隔，不是服务端承诺的有效期。客户端在 SDK 登录满十二小时后重连会重新登录；迁移临时 sid 本身无法长期使用。

Windows 完成上面的本机导出并正常关闭游戏后，在交互式终端执行：

```powershell
conda run --no-capture-output -n airidev python plugins/airi_astral_party/account_tool.py --login
conda run --no-capture-output -n airidev python plugins/airi_astral_party/account_tool.py --check
```

工具提示输入飞魔手机号和密码，均不回显，不提供密码命令行参数。登录成功后保存手机号、飞魔账号标识、密码派生值和游戏会话；不保存原始密码。派生值为官方 SDK 使用的 `md5(password + md5(password))`，具有密码等价权限，必须作为密码保管，不能公开、提交 Git 或发送给 Bot。Windows 写入时设置用户专用 ACL，Linux 写入时设置权限 600；使用文件锁、临时文件、原子替换和文件/目录同步保存。

`app_id` 与签名参数必须配套：当前适配客户端默认飞魔配置 `110001950`，以及已解析安装渠道配置 `110001958`。二者均走飞魔手机号密码接口；安装渠道标识不等同于账号类型。工具按现有 `app_id` 选择配套签名，不会只改签名或擅自改写 `game_id`、`channel_id`、`app_id`。若服务端不接受当前渠道的飞魔账号，应从可正常登录该账号的官方客户端重新导出对应配置；跨渠道角色互通尚未验证。

将最新的 `data/astral_party/config.json` 通过 SSH/SCP 传到生产机，以运行 Airi 的用户保存。以下假设部署目录为 `/opt/AiriCore`，Python 为 `/opt/AiriCore/.venv/bin/python`，请替换为实际路径：

```sh
cd /opt/AiriCore
chmod 700 data/astral_party
chmod 600 data/astral_party/config.json
/opt/AiriCore/.venv/bin/python plugins/airi_astral_party/account_tool.py --check
/opt/AiriCore/.venv/bin/python plugins/airi_astral_party/account_tool.py --refresh
```

生产机使用已安装 AiriCore 依赖的 Python 环境，无需 Windows、图形界面、游戏客户端或 Miniconda。配置不绑定 Windows DPAPI、注册表或密钥链。迁移后保留配置中的设备标识和 SDK 协议设备字段；`os=windows` 是所还原客户端协议字段，不是生产机平台检测结果。

用运行 Airi 的用户执行 `crontab -e`，每小时检查一次：

```cron
17 * * * * cd /opt/AiriCore && /opt/AiriCore/.venv/bin/python plugins/airi_astral_party/account_tool.py --refresh >> /opt/AiriCore/logs/astral-account.log 2>&1
```

预先创建可写的 `logs` 目录并配置日志轮转。`--refresh` 未到六小时直接退出，到期后调用飞魔 `/account/authorize` 重新登录，校验返回的飞魔账号标识一致后原子更新 sid。请求失败或保存失败不会丢失原有密码派生凭据，下一次可重新登录。Bot 下次查询会重读配置，无需重启；`astral status` 仅显示本地配置状态，不主动验证服务端授权。

失败退出码为 1，请纳入生产机现有监控。只在生产机启用定时任务，避免两台机器重复登录；迁移后关闭开发机游戏。密码修改、账号限制、身份验证或协议升级仍可能要求在官方客户端处理后重新执行 `--login`，Linux 交互式终端同样支持该命令。凭据可重复登录的设计不代表服务端承诺永久有效。

首次部署需实际验证玩家查询、跨越十二小时的多次定时登录、停机重启后的恢复。当前仅在 Windows 的 airidev 环境完成离线协议和文件持久化测试，没有真实 Linux 运行环境或账号联调结果。

每次查询建立短连接，完成官方登录和读取后关闭；多人请求串行，繁忙时提示稍后重试。账号应专用于查询，避免与正在游玩的同一账号竞争登录。配置与绑定目录已从 Git 排除，错误与日志不输出凭据。

## 数据范围与界面

实际调用 `SearchPlayer 5185→5186`、`GetShowPlayer 5153→5154`、`GetPlayerFightRecord 5155→5156`。仅开放以 UID 查询的展示资料；不会查询、发送或修改登录账号的邮件、私聊、背包、抽卡、商城、房间或公会状态。`isShowData`、`isShowFight` 关闭时，即使服务器仍返回字段，也不会展示或进一步查询详情。

生涯统计包括累计参与局数、胜利局数、拥有角色数、最常用角色、装扮数、皮肤数。详情包含各参赛者昵称、使用角色、名次、星级、金币、玩家等级及放弃标记。记录数量以服务器实际返回为准，最多处理最近 100 场；并非完整历史库。未发现独立玩家排行榜或生涯伤害、击杀查询接口。

个人卡片沿用游戏账号界面的布局与切图，使用固定帕露南主题并在图片标明；不把主题立绘当作玩家设置。对局角色图示来自游戏角色头像，未知角色显示问号，不冒充玩家自定义头像。图片中不使用外部插画、生成式图片或网页素材。所有帮助、成功和错误提示也以图片发送；OneBot 图片使用 Base64。所有图片右下角统一添加小号半透明文字水印 `Generated By AiriCore`，使用游戏内 Impact 字体。

## 解析来源与验证边界

来源为本机 CN_TAPTAP V3.2.1 安装文件及已下载的 Addressables 更新缓存。`assets/manifest.json` 记录素材原始资源名、包名与导出文件 SHA-256；`assets/protocol.desc` 保存从客户端反射信息还原的 Protobuf 描述符，保留 `sfixed64` / `sfixed32`、枚举、map 等精确语义。UI 坐标取自 FairyGUI 二进制。

素材已经随插件附带，正常查询无需安装游戏或 UnityPy。更新素材时可在安装 UnityPy 与 Pillow 的离线维护环境执行下列导出命令；`--cache-dir` 指向 Addressables 缓存中的 `AssetBundles`，`--catalog` 使用同版本资源目录文件，`--output` 建议先指向新建目录，核对后再替换插件素材：

```powershell
conda run -n airidev python plugins/airi_astral_party/export_assets.py --game-dir "游戏安装目录" --cache-dir "缓存目录/AssetBundles" --catalog "catalog_3.2.1.json" --output "导出目录"
```

导出脚本不读取账号凭据、不访问网络，也不重建通信描述符；协议更新需要重新检查当前版本程序集中的反射描述符与 RPC 调用。

按本次开发要求，完成离线验证后再配置专用账号。当前已验证本地 TCP 模拟服务、真实协议序列化、隐私处理、绑定存储、图片合成和插件加载；尚未使用真实账号联调。在线权限、服务端数据完整性、实际凭据寿命和未来版本兼容性待首次部署验证，不应把静态协议还原视为在线查询成功。

开发验证：`conda run -n airidev python -m unittest discover -s tests -p "test_astral_party*.py" -v`。测试不连接游戏服务器，也不会读取本机游戏账号凭据。

# Shared Game Authentication UI Design

## Goal

勇闯未知 SEKAI 与 Point Salad 的静态网页使用同一套网页认证体验。登录入口固定在页面右上角，点击后打开覆盖层弹窗，由用户选择 Bot 验证登录或邮箱验证登录。两个站点继续只通过 HTTPS 调用 `https://ws.airi.asia:22319`，不依赖静态站点服务端或 AiriCore 本地文件。

## Shared Component

两个静态项目各自发布一份内容相同的 `js/auth.js` 和认证样式。组件暴露 `AiriGameAuth`，维护 token、QQ 号、昵称和会话恢复，且不包含任何游戏专有接口。

会话字段保存在 localStorage 的共享键 `airi_game_token`、`airi_game_qq`、`airi_game_nick`。组件启动时调用 `GET /api/me` 校验既有 token；网络不可达时保留本地会话但将其标记为暂不可用，401 时清除会话并更新右上角状态。

每页 HTML 都提供 `#auth-bar`、`#toast-layer` 和 `#auth-modal-root`。组件渲染右上角入口、欢迎状态、退出入口和一次仅存在一个的认证弹窗。两站沿用一致的 DOM 语义、文案和动画；游戏自己的视觉主题仅通过 CSS 变量改变颜色和字体。

## Login Flow

打开弹窗后的初始页面显示两个等权选项。

Bot 验证：调用 `POST /api/auth/request` 获取绑定码，在弹窗中显示 `登录网页<code>`、剩余有效时间和取消按钮。组件每两秒调用 `GET /api/auth/poll?code=`，成功后持久化 token、昵称和 QQ 号，关闭弹窗并触发认证状态事件。超时、取消和网络失败均保留可重新开始的登录选项。

邮箱验证：用户填写严格的 `QQ号@qq.com`，调用 `POST /api/auth/email/request`。成功后进入验证码输入状态，调用 `POST /api/auth/email/confirm` 完成登录。按钮在请求期间禁用，显示服务端返回的可读错误，验证码不写入 localStorage。

组件向 `window` 分发 `airi-game-auth-change` 事件，事件 detail 包含 `{ loggedIn, token, qq, nick, reachable }`。游戏页面据此刷新自己的房间或在线功能；组件不会创建、加入或操作任何游戏房间。

## Point Salad HTML5 Interface

Point Salad 保持独立静态部署，并把插件内已经生成的六名角色立绘、Q 版角色和底图复制到其发布素材目录。游戏不请求或暴露 AiriCore 插件的文件路径。

登录后显示大厅，可创建快速原版或标准混合房间、输入房间码加入，并显示当前账号。进入房间后桌面包含稳定的市场牌列、玩家区、当前回合区和上下文操作区。卡牌用实际卡面、角色素材及牌面信息渲染，不再使用编号色块。每一个可操作目标均为原生 button：计分牌单选、角色牌最多双选、翻牌、技能、开始、离开、结束和生成房间码。

客户端仅根据服务器快照决定可操作目标，实际规则和权限继续由 22319 API 负责。提交操作时目标进入 pending 状态，成功后以新快照替换视图，失败后恢复选择并展示错误。当前玩家、市场补牌、手牌变动和回合提示使用 opacity 与 transform 动画；`prefers-reduced-motion` 禁用非必要动画。移动端以单列信息和横向可滚动的牌列呈现，所有按钮和文字不发生重叠。

每五秒在页面可见且用户已进入房间时拉取快照并发送 heartbeat。认证失效时停止心跳和轮询，保留本地房间码并回到登录前的可恢复状态。网页房间不向群聊发送消息；群聊房间沿用服务端已有的「网页活跃时改发网页继续操作」通知策略。

## Compatibility

勇闯未知 SEKAI 从现有的 `SekaiAuth` 和局部登录弹窗迁移到 `AiriGameAuth`，保留它现有的在线/离线模式与积分、存档 API 调用。为避免破坏游戏引擎，兼容层继续提供它当前使用的 `isLoggedIn`、`refresh`、`logout`、`token`、`nick`、`qq` 及 SEKAI 专属积分和存档 API。

邮箱登录成为 SEKAI 与 Point Salad 均可使用的账号入口。两种方式签发相同 token，因此帐号、昵称、网页房间和 SEKAI 在线数据的身份语义一致。

## Verification

验证包括：两个站点的未登录、Bot 登录成功/取消/过期、邮箱发送/确认/错误、会话恢复与 401 登出；静态资源无本地路径引用；Point Salad 创建、加入、开始、选牌、翻牌、技能、房间码和心跳 API 的交互；桌面与移动视口下的 Playwright 截图和基本操作；以及 AiriCore 中 game server 的认证与 Point Salad API 聚焦测试。

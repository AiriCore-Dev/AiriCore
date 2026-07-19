# airi_wish_bottle 邮件模板说明

## 文件结构

```
plugins/airi_wish_bottle/
├── templates/
│   └── base.html                    # HTML 邮件基础模板
├── base/
│   ├── email_template.py            # 邮件渲染器（6 种审核结果）
│   ├── helpers.py                   # send_email 现支持 HTML
│   └── persistence.py               # SMTP 发送逻辑（multipart/alternative）
└── handlers/
    └── admin.py                     # 审核命令调用渲染器
```

## 设计风格

- 主色：`#ffaacc` / `#e85d9a`（桃井爱莉粉）
- 通过审核徽章：`#1fae7a` 绿色
- 未通过徽章：`#e85d9a` 粉色
- 字体：Segoe UI / Arial（邮件客户端通用）
- 布局：table-based（兼容 Outlook / 各邮件客户端）
- 响应式：移动端自适应
- 暗色模式：系统偏好自动切换

## 邮件类型（6 种）

| 类型 | 函数 | 参数 |
|-----|------|------|
| 心愿瓶审核通过 | `render_bottle_result(name, content, unique_id, True)` | 昵称、内容、编号、通过 |
| 心愿瓶审核未通过 | `render_bottle_result(name, content, unique_id, False)` | 昵称、内容、编号、拒绝 |
| 评论审核通过 | `render_comment_result(name, content, unique_id, True)` | 昵称、评论、编号、通过 |
| 评论审核未通过 | `render_comment_result(name, content, unique_id, False)` | 昵称、评论、编号、拒绝 |
| 举报审核通过 | `render_report_result(name, unique_id, target_id, True)` | 昵称、举报编号、被举报编号、通过 |
| 举报审核未通过 | `render_report_result(name, unique_id, target_id, False)` | 昵称、举报编号、被举报编号、拒绝 |

所有函数返回 `(subject: str, plain_text: str, html_body: str)` 三元组。

## 邮件结构

每封邮件包含：
1. **Header banner**：粉色渐变 + Airi Wish Bottle logo
2. **状态徽章**：通过（绿）/ 未通过（粉）
3. **主标题**：审核结果
4. **正文段落**：称呼 + 审核说明
5. **内容卡片**：心愿瓶内容 / 评论内容（自动截断 >60 字）
6. **编号标识**：monospace 字体编号
7. **申诉提示**（拒绝时）：引导三日内申诉至 `saki@saki.ln.cn`
8. **奖励提示**（举报通过时）：绿色提示框，说明凭邮件申领自定义编号心愿瓶
9. **Footer**：AiriCore Dev. 官网 + GitHub + 自动发送提示

## 技术要点

### 1. 邮件 HTML 规范
- 使用 `<table>` 布局（不是 `div + flex`）
- 所有样式行内化（`style="..."`）
- 图片使用绝对 URL（`https://www.airi.asia/assets/images/icon.avif`）
- 包含 preheader 隐藏文本（邮件预览）
- 兼容 Outlook VML 按钮（`<!--[if mso]>` 条件注释）

### 2. multipart/alternative
`persistence.py` 的 `save_to_json` 在关闭时批量发送邮件：
- 检测 `mail[3]`（html_body）是否存在
- 存在时构建 `MIMEMultipart('alternative')`，先附加 plain 再附加 html
- 不存在时回退纯文本 `MIMEText(mail[2], 'plain')`

邮件客户端优先显示 HTML，不支持时降级显示纯文本。

### 3. 内容截断与转义
- `_shorten(text, limit=60)`：内容超过 60 字截断 + `"......"`
- `_esc(text)`：HTML 转义 + `\n` 转 `<br />`
- `_plain(name, lines, appeal=False)`：纯文本生成，缩进 + 申诉提示

### 4. 调用示例（admin.py）

```python
from ..base.email_template import render_bottle_result

# 审核通过
subj, plain, html_body = render_bottle_result(
    state.data["bottles"][unique_id]["owner"],
    state.data["bottles"][unique_id]["content"],
    unique_id,
    True
)
send_email(
    f'{state.data["bottles"][unique_id]["owner_id"]}@qq.com',
    subj,
    plain,
    html_body
)
```

## 修改指南

### 更改主色调
编辑 `base/email_template.py`：
```python
FONT = "'Segoe UI', Arial, sans-serif"
APPEAL_MAIL = "saki@saki.ln.cn"
```
搜索 `#ffaacc` / `#e85d9a` / `#1fae7a` 替换即可。

### 更改 logo 或网址
编辑 `templates/base.html`：
- Logo：第 61 行 `<img src="https://www.airi.asia/assets/images/icon.avif" ...>`
- 官网：第 81 行 `<a href="https://www.airi.asia" ...>`
- GitHub：第 83 行 `<a href="https://github.com/AiriCore-Dev/AiriCore" ...>`

### 更改邮件文案
编辑 `base/email_template.py` 对应函数内的 `_paragraph(...)` / `_hint(...)` 调用。

### 测试渲染
```python
from plugins.airi_wish_bottle.base import email_template as et

subject, plain, html = et.render_bottle_result('田麻小溪', '测试内容', 'test1234', True)
with open('/tmp/test.html', 'w', encoding='utf-8') as f:
    f.write(html)
# 浏览器打开 /tmp/test.html 预览
```

## 兼容性

已测试：
- Gmail（桌面 + 移动端）
- QQ 邮箱（网页版 + 客户端）
- Outlook（网页版 + 桌面客户端）
- Apple Mail
- 163 / 126 邮箱

暗色模式：
- 通过 `@media (prefers-color-scheme: dark)` 自动适配
- 主色调保留粉色，背景切换为深色

## 注意事项

1. **不要在 HTML 中使用 emoji / Unicode 特殊符号**（Windows GBK 环境限制）
2. **修改 base.html 后需重启 bot**（模板在首次加载时缓存到 `_base_cache`）
3. **SMTP 发送在 bot 关闭时执行**（`@driver.on_shutdown`），测试时需完整关闭 bot
4. **邮件队列在内存**（`state.email_list`），关闭前崩溃会丢失未发送邮件
5. **头像图片走公网 CDN**（`www.airi.asia`），离线环境图片会 broken

## FAQ

**Q: 如何在本地预览邮件效果？**  
A: 运行测试脚本渲染 HTML 后用浏览器打开，或发送测试邮件到自己邮箱。

**Q: 邮件被识别为垃圾邮件？**  
A: 确保 SMTP 配置正确（发件人域名 SPF/DKIM 记录），避免短时间大量发送。

**Q: 可以添加附件吗？**  
A: 当前不支持，如需附件需修改 `persistence.py` 的 `save_to_json` 函数。

**Q: 如何支持更多语言？**  
A: 在 `email_template.py` 增加语言参数，根据语言返回不同文案的 HTML。

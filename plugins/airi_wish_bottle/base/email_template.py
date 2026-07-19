import os
import html
import hashlib

_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_base_cache = None

FONT = "'Segoe UI', Arial, sans-serif"
APPEAL_MAIL = "airicore@saki.ln.cn"


def _load_base():
    global _base_cache
    if _base_cache is None:
        with open(os.path.join(_BASE_DIR, "base.html"), "r", encoding="utf-8") as f:
            _base_cache = f.read()
    return _base_cache


def _esc(text):
    return html.escape(str(text)).replace("\n", "<br />")


def _md5(text):
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()


def _badge(text, approved):
    if approved:
        bg, fg = "#e6f7f0", "#1fae7a"
    else:
        bg, fg = "#fde8f0", "#e85d9a"
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 18px 0;">'
        '<tr><td class="bg-badge" bgcolor="' + bg + '" style="background-color:' + bg + '; '
        'border-radius:999px; padding:7px 18px; font-family:' + FONT + '; font-size:13px; '
        'font-weight:700; color:' + fg + ';">' + _esc(text) + '</td></tr></table>'
    )


def _hero(badge_text, approved, title):
    return (
        '<tr><td class="px content-bg" style="padding:38px 40px 4px 40px; background-color:#ffffff;">'
        + _badge(badge_text, approved) +
        '<h1 class="h1 text-primary" style="margin:0; padding:0; background-color:transparent; '
        'font-family:' + FONT + '; font-size:26px; line-height:36px; font-weight:700; color:#2b2b33;">'
        + _esc(title) + '</h1></td></tr>'
    )


def _paragraph(text, top=16):
    return (
        '<tr><td class="px" style="padding:' + str(top) + 'px 40px 0 40px;">'
        '<p class="text-secondary" style="margin:0; font-family:' + FONT + '; font-size:15px; '
        'line-height:26px; color:#55555f;">' + _esc(text) + '</p></td></tr>'
    )


def _content_card(label, content, use_hash=False):
    display_content = _md5(content) if use_hash else _esc(content)
    return (
        '<tr><td class="px" style="padding:22px 40px 0 40px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="bg-card" '
        'style="background-color:#fbf5f9; border-radius:12px; border-left:4px solid #ff7fb3;">'
        '<tr><td style="padding:18px 20px;">'
        '<div class="text-muted" style="font-family:' + FONT + '; font-size:12px; font-weight:700; '
        'color:#9a9aa4; letter-spacing:0.5px; padding-bottom:8px;">' + _esc(label) + '</div>'
        '<div class="text-secondary" style="font-family:' + ('\'JetBrains Mono\', Consolas, monospace' if use_hash else FONT) + '; font-size:' + ('13px' if use_hash else '15px') + '; line-height:25px; '
        'color:#55555f; word-break:break-word;">' + display_content + '</div>'
        '</td></tr></table></td></tr>'
    )


def _id_row(unique_id):
    return (
        '<tr><td class="px" style="padding:18px 40px 0 40px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td class="text-muted" style="font-family:' + FONT + '; font-size:13px; color:#9a9aa4; '
        'padding-right:10px;">编号</td>'
        '<td class="bg-badge" bgcolor="#fde8f0" style="background-color:#fde8f0; border-radius:8px; '
        'padding:5px 14px; font-family:\'JetBrains Mono\', Consolas, monospace; font-size:15px; '
        'font-weight:700; color:#e85d9a; letter-spacing:1px;">' + _esc(unique_id) + '</td>'
        '</tr></table></td></tr>'
    )


def _reward_box(text):
    return (
        '<tr><td class="px" style="padding:20px 40px 0 40px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#e6f7f0; border-radius:12px;">'
        '<tr><td style="padding:16px 20px; font-family:' + FONT + '; font-size:14px; line-height:24px; '
        'color:#1fae7a; font-weight:600;">' + _esc(text) + '</td></tr></table></td></tr>'
    )


def _hint(text):
    return (
        '<tr><td class="px" style="padding:20px 40px 0 40px;">'
        '<p class="link-hint text-muted" style="margin:0; padding:14px 16px; background-color:#fbf5f9; '
        'border-radius:10px; font-family:' + FONT + '; font-size:12px; line-height:20px; color:#9a9aa4;">'
        + text.replace("{MAIL}", '<span style="color:#e85d9a; font-weight:700;">' + APPEAL_MAIL + '</span>') +
        '</p></td></tr>'
    )


def _closing():
    return (
        '<tr><td class="px" style="padding:26px 40px 40px 40px;">'
        '<p class="text-tertiary" style="margin:0; font-family:' + FONT + '; font-size:14px; '
        'line-height:24px; color:#77777f;">此致</p>'
        '<p class="text-primary" style="margin:4px 0 0 0; font-family:' + FONT + '; font-size:15px; '
        'font-weight:700; color:#2b2b33;">AiriCore Dev.</p></td></tr>'
    )


def _wrap(title, preheader, content):
    return (
        _load_base()
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{PREHEADER}}", html.escape(preheader))
        .replace("{{CONTENT}}", content)
    )


def _shorten(text, limit=60):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "......"


def _plain(name, lines, appeal=False):
    out = "尊敬的 " + str(name) + "：\n"
    for line in lines:
        out += "    " + line + "\n"
    if appeal:
        out += "    如果对审核结果有异议，可于收到该邮件三日内发送邮件至 " + APPEAL_MAIL + " 申请复核。\n"
    out += "\n此致，\nAiriCore Dev."
    return out


def render_bottle_result(name, content, unique_id, approved):
    content_hash = _md5(content)
    if approved:
        subject = "您的心愿瓶 " + str(unique_id) + " 已通过审核"
        body = (
            _hero("审核通过", True, "心愿瓶已通过审核")
            + _paragraph("尊敬的 " + str(name) + "：")
            + _paragraph("您投放的心愿瓶已通过人工审核，现已正式漂流在心愿之海中，等待有缘人开启。感谢使用 Airi 心愿瓶。")
            + _content_card("心愿内容（MD5）", content, use_hash=True)
            + _id_row(unique_id)
            + _closing()
        )
        plain = _plain(name, [
            "您投放的心愿瓶（MD5：" + content_hash + "）已通过人工审核，编号为 " + str(unique_id) + " ，现已正式漂流在心愿之海中。感谢使用 Airi 心愿瓶。",
        ])
    else:
        subject = "您的心愿瓶 " + str(unique_id) + " 未通过审核"
        body = (
            _hero("审核未通过", False, "心愿瓶未通过审核")
            + _paragraph("尊敬的 " + str(name) + "：")
            + _paragraph("很抱歉，您投放的心愿瓶未能通过人工审核，暂时无法漂流。")
            + _content_card("心愿内容（MD5）", content, use_hash=True)
            + _hint("如果对审核结果有异议，可于收到该邮件三日内发送邮件至 {MAIL} 申请复核。")
            + _closing()
        )
        plain = _plain(name, [
            "很抱歉，您投放的心愿瓶（MD5：" + content_hash + "）未通过人工审核，暂时无法漂流。",
        ], appeal=True)
    return subject, plain, _wrap(subject, subject, body)


def render_comment_result(name, content, unique_id, approved):
    content_hash = _md5(content)
    if approved:
        subject = "您的评论 " + str(unique_id) + " 已通过审核"
        body = (
            _hero("审核通过", True, "评论已通过审核")
            + _paragraph("尊敬的 " + str(name) + "：")
            + _paragraph("您发表的评论已通过人工审核，现已展示在对应心愿瓶下。感谢使用 Airi 心愿瓶。")
            + _content_card("评论内容（MD5）", content, use_hash=True)
            + _closing()
        )
        plain = _plain(name, [
            "您发表的评论（MD5：" + content_hash + "）已通过人工审核，现已展示在对应心愿瓶下。感谢使用 Airi 心愿瓶。",
        ])
    else:
        subject = "您的评论 " + str(unique_id) + " 未通过审核"
        body = (
            _hero("审核未通过", False, "评论未通过审核")
            + _paragraph("尊敬的 " + str(name) + "：")
            + _paragraph("很抱歉，您发表的评论未能通过人工审核，暂时无法展示。")
            + _content_card("评论内容（MD5）", content, use_hash=True)
            + _hint("如果对审核结果有异议，可于收到该邮件三日内发送邮件至 {MAIL} 申请复核。")
            + _closing()
        )
        plain = _plain(name, [
            "很抱歉，您发表的评论（MD5：" + content_hash + "）未通过人工审核，暂时无法展示。",
        ], appeal=True)
    return subject, plain, _wrap(subject, subject, body)


def render_report_result(name, unique_id, target_id, approved):
    if approved:
        subject = "您的举报 " + str(unique_id) + " 已通过审核"
        body = (
            _hero("举报成立", True, "举报已通过审核")
            + _paragraph("尊敬的 " + str(name) + "：")
            + _paragraph("您举报的心愿瓶经核实，违规情况成立，开发团队已依规处理该心愿瓶。感谢您为 AiriCore 做出的贡献。")
            + _id_row(target_id)
            + _reward_box("凭该邮件可申领自定义编号心愿瓶一个，请联系 " + APPEAL_MAIL + "。")
            + _closing()
        )
        plain = _plain(name, [
            "您举报的编号为 " + str(target_id) + " 的心愿瓶经核实，违规情况成立，开发团队已依规处理该心愿瓶。感谢您为 AiriCore 做出的贡献。",
            "凭该邮件可申领自定义编号心愿瓶一个，请联系 " + APPEAL_MAIL + "。",
        ])
    else:
        subject = "您的举报 " + str(unique_id) + " 未通过审核"
        body = (
            _hero("举报未成立", False, "举报未通过审核")
            + _paragraph("尊敬的 " + str(name) + "：")
            + _paragraph("您举报的心愿瓶经核实，未发现违规情况，请谅解。")
            + _id_row(target_id)
            + _hint("如果对审核结果有异议，可于收到该邮件三日内发送邮件至 {MAIL} 申请复核。")
            + _closing()
        )
        plain = _plain(name, [
            "您举报的编号为 " + str(target_id) + " 的心愿瓶经核实，未发现违规情况，请谅解。",
        ], appeal=True)
    return subject, plain, _wrap(subject, subject, body)

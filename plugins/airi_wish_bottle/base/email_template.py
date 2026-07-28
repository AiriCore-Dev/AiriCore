import hashlib

from utils import email_template as et

APPEAL_MAIL = "airicore@saki.ln.cn"
_APPEAL_TEXT = "如果对审核结果有异议，可于收到该邮件三日内发送邮件至 {MAIL} 申请复核。"


def _md5(text):
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


def _appeal_row():
    return et.hint_row(
        et.esc("如果对审核结果有异议，可于收到该邮件三日内发送邮件至 ")
        + et.emphasis(APPEAL_MAIL)
        + et.esc(" 申请复核。")
    )


def _head(badge_text, approved, title, name):
    return (
        et.badge_row(badge_text, approved)
        + et.title_row(title, top=16)
        + et.paragraph_row(f"尊敬的 {name}：", top=18)
    )


def _plain(name, lines, appeal=False):
    out = "尊敬的 " + str(name) + "：\n"
    for line in lines:
        out += "    " + line + "\n"
    if appeal:
        out += "    " + _APPEAL_TEXT.replace("{MAIL}", APPEAL_MAIL) + "\n"
    out += "\n此致，\nAiriCore Dev."
    return out


def render_bottle_result(name, content, unique_id, approved):
    content_hash = _md5(content)
    if approved:
        subject = "您的心愿瓶 " + str(unique_id) + " 已通过审核"
        body = (
            _head("审核通过", True, "心愿瓶已通过审核", name)
            + et.paragraph_row("您投放的心愿瓶已通过人工审核，现已正式漂流在心愿之海中，等待有缘人开启。感谢使用 Airi 心愿瓶。")
            + et.card_row("心愿内容（MD5）", content_hash, mono=True)
            + et.id_row("编号", unique_id)
            + et.closing_row()
        )
        plain = _plain(name, [
            "您投放的心愿瓶（MD5：" + content_hash + "）已通过人工审核，编号为 " + str(unique_id) + " ，现已正式漂流在心愿之海中。感谢使用 Airi 心愿瓶。",
        ])
    else:
        subject = "您的心愿瓶 " + str(unique_id) + " 未通过审核"
        body = (
            _head("审核未通过", False, "心愿瓶未通过审核", name)
            + et.paragraph_row("很抱歉，您投放的心愿瓶未能通过人工审核，暂时无法漂流。")
            + et.card_row("心愿内容（MD5）", content_hash, mono=True)
            + _appeal_row()
            + et.closing_row()
        )
        plain = _plain(name, [
            "很抱歉，您投放的心愿瓶（MD5：" + content_hash + "）未通过人工审核，暂时无法漂流。",
        ], appeal=True)
    return subject, plain, et.wrap(subject, subject, body)


def render_comment_result(name, content, unique_id, approved):
    content_hash = _md5(content)
    if approved:
        subject = "您的评论 " + str(unique_id) + " 已通过审核"
        body = (
            _head("审核通过", True, "评论已通过审核", name)
            + et.paragraph_row("您发表的评论已通过人工审核，现已展示在对应心愿瓶下。感谢使用 Airi 心愿瓶。")
            + et.card_row("评论内容（MD5）", content_hash, mono=True)
            + et.closing_row()
        )
        plain = _plain(name, [
            "您发表的评论（MD5：" + content_hash + "）已通过人工审核，现已展示在对应心愿瓶下。感谢使用 Airi 心愿瓶。",
        ])
    else:
        subject = "您的评论 " + str(unique_id) + " 未通过审核"
        body = (
            _head("审核未通过", False, "评论未通过审核", name)
            + et.paragraph_row("很抱歉，您发表的评论未能通过人工审核，暂时无法展示。")
            + et.card_row("评论内容（MD5）", content_hash, mono=True)
            + _appeal_row()
            + et.closing_row()
        )
        plain = _plain(name, [
            "很抱歉，您发表的评论（MD5：" + content_hash + "）未通过人工审核，暂时无法展示。",
        ], appeal=True)
    return subject, plain, et.wrap(subject, subject, body)


def render_report_result(name, unique_id, target_id, approved):
    if approved:
        subject = "您的举报 " + str(unique_id) + " 已通过审核"
        body = (
            _head("举报成立", True, "举报已通过审核", name)
            + et.paragraph_row("您举报的心愿瓶经核实，违规情况成立，开发团队已依规处理该心愿瓶。感谢您为 AiriCore 做出的贡献。")
            + et.id_row("编号", target_id)
            + et.highlight_row("凭该邮件可申领自定义编号心愿瓶一个，请联系 " + APPEAL_MAIL + "。")
            + et.closing_row()
        )
        plain = _plain(name, [
            "您举报的编号为 " + str(target_id) + " 的心愿瓶经核实，违规情况成立，开发团队已依规处理该心愿瓶。感谢您为 AiriCore 做出的贡献。",
            "凭该邮件可申领自定义编号心愿瓶一个，请联系 " + APPEAL_MAIL + "。",
        ])
    else:
        subject = "您的举报 " + str(unique_id) + " 未通过审核"
        body = (
            _head("举报未成立", False, "举报未通过审核", name)
            + et.paragraph_row("您举报的心愿瓶经核实，未发现违规情况，请谅解。")
            + et.id_row("编号", target_id)
            + _appeal_row()
            + et.closing_row()
        )
        plain = _plain(name, [
            "您举报的编号为 " + str(target_id) + " 的心愿瓶经核实，未发现违规情况，请谅解。",
        ], appeal=True)
    return subject, plain, et.wrap(subject, subject, body)

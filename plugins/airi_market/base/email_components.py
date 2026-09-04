import html

from utils.email import load_base

FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"
TEXT_BODY = "#3a3a3c"
TEXT_MUTED = "#86868b"
TEXT_FAINT = "#aeaeb2"
TINT_BG = "#fff0f5"
SOFT_BG = "#fff5f8"
ACCENT = "#ffaacc"


def esc(text):
    return html.escape(str(text))


def wrap(title, preheader, content):
    return load_base().replace("{{TITLE}}", esc(title)).replace("{{PREHEADER}}", esc(preheader)).replace("{{CONTENT}}", content)


def cover_row(cover_url):
    return (
        '<tr><td style="padding:0; line-height:0;">'
        f'<img src="{esc(cover_url)}" width="600" alt="封面"'
        ' style="width:100%; max-width:600px; height:auto; max-height:260px;'
        ' object-fit:cover; display:block; border:0;" />'
        "</td></tr>"
    )


def note_row(text):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:32px 48px 0 48px; background-color:#ffffff;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:13px;'
        f' line-height:20px; color:{TEXT_MUTED}; letter-spacing:0.01em;">'
        + esc(text)
        + "</p></td></tr>"
    )


def title_row(title, top=12):
    return (
        '<tr><td class="px content-bg"'
        f' style="padding:{top}px 48px 10px 48px; background-color:#ffffff;">'
        '<h1 class="h1"'
        f' style="margin:0; padding:0; font-family:{FONT}; font-size:26px;'
        f' line-height:1.15; font-weight:700; letter-spacing:-0.02em; color:#1d1d1f;">'
        + esc(title)
        + "</h1></td></tr>"
    )


def article_body_row(html_content):
    body_style = (
        f"font-family:{FONT}; font-size:15px; line-height:1.75;"
        f" color:{TEXT_BODY}; letter-spacing:0;"
    )
    return (
        '<tr><td class="px content-bg" style="padding:18px 48px 36px 48px; background-color:#ffffff;">'
        + _ARTICLE_CSS
        + f'<div class="article-body" style="{body_style}">'
        + html_content
        + "</div></td></tr>"
    )


_ARTICLE_CSS = (
    "<style>"
    f".article-body{{font-family:{FONT};}}"
    ".article-body h2{font-size:17px;font-weight:700;color:#1d1d1f;"
    "letter-spacing:-0.01em;line-height:1.3;"
    "border-bottom:2px solid #ffaacc;padding-bottom:5px;"
    "margin:1.8em 0 .5em 0;padding:0 0 5px 0;}"
    ".article-body h3{font-size:15px;font-weight:600;color:#1d1d1f;"
    "letter-spacing:-0.005em;margin:1.4em 0 .4em 0;}"
    ".article-body p{margin:.6em 0 .6em 0;}"
    ".article-body img{max-width:100%;height:auto;border-radius:12px;"
    "margin:14px 0;display:block;}"
    ".article-body a{color:#ffaacc;text-decoration:none;}"
    ".article-body blockquote{margin:18px 0;padding:14px 20px;"
    "background:#fff5f8;border-left:3px solid #ffaacc;"
    "border-radius:0 8px 8px 0;color:#6e6e73;}"
    ".article-body code{background:#f2f2f7;padding:2px 6px;border-radius:5px;"
    "font-family:'Menlo','Courier New',monospace;font-size:13px;color:#1d1d1f;}"
    ".article-body pre{background:#f2f2f7;padding:18px 20px;"
    "border-radius:12px;overflow-x:auto;margin:16px 0;}"
    ".article-body pre code{background:none;padding:0;color:#3a3a3c;font-size:13px;"
    "line-height:1.6;}"
    ".article-body table{width:100%;border-collapse:collapse;margin:18px 0;"
    "font-size:14px;}"
    ".article-body th{background:#f2f2f7;color:#1d1d1f;font-weight:600;"
    "padding:10px 14px;border:1px solid #e5e5ea;text-align:left;}"
    ".article-body td{padding:9px 14px;border:1px solid #e5e5ea;color:#3a3a3c;}"
    ".article-body hr{border:none;border-top:1px solid #e5e5ea;margin:28px 0;}"
    ".article-body strong{font-weight:600;color:#1d1d1f;}"
    "@media(prefers-color-scheme:dark){"
    ".article-body{color:#ebebf5;}"
    ".article-body h2,.article-body h3,.article-body strong{color:#f5f5f7;}"
    ".article-body blockquote{background:#2c2c2e;border-left-color:#48484a;"
    "color:#98989d;}"
    ".article-body code{background:#2c2c2e;color:#f5f5f7;}"
    ".article-body pre{background:#2c2c2e;}"
    ".article-body pre code{color:#ebebf5;}"
    ".article-body th{background:#2c2c2e;color:#f5f5f7;border-color:#3a3a3c;}"
    ".article-body td{border-color:#3a3a3c;color:#ebebf5;}"
    ".article-body hr{border-top-color:#3a3a3c;}"
    "}"
    "</style>"
)


def contact_tip_row():
    return (
        '<tr><td class="px" style="padding:24px 48px 18px 48px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td style="background-color:{TINT_BG}; border-radius:10px; padding:14px 18px;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:13px; color:{TEXT_BODY}; line-height:20px; letter-spacing:0.005em;">'
        "建议将本邮件发件人添加到联系人，确保后续通知能正常送达收件箱。"
        "</p></td></tr></table></td></tr>"
    )


def unsubscribe_row(unsubscribe_url):
    return (
        '<tr><td style="padding:8px 48px 32px 48px; text-align:center;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="border-top:1px solid #f2f2f7; padding-top:22px; text-align:center;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 10px auto;"><tr>'
        f'<td style="border:1px solid {ACCENT}; border-radius:7px; padding:9px 24px; background-color:{SOFT_BG};">'
        f'<a href="{esc(unsubscribe_url)}" style="font-family:{FONT}; font-size:13px; color:{TEXT_BODY}; text-decoration:none; display:block; white-space:nowrap; letter-spacing:0.005em;">退订此类邮件</a>'
        "</td></tr></table>"
        f'<p style="margin:0; font-family:{FONT}; font-size:11px; color:{TEXT_FAINT}; line-height:18px; letter-spacing:0.01em;">'
        "点击退订后将不再收到此类邮件，操作即时生效。"
        "</p></td></tr></table></td></tr>"
    )


__all__ = [
    "article_body_row",
    "contact_tip_row",
    "cover_row",
    "note_row",
    "title_row",
    "unsubscribe_row",
    "wrap",
]

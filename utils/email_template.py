import os
import html as html_lib

FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "'Menlo', 'Courier New', monospace"
ACCENT = "#ffaacc"
ACCENT_DARK = "#e85d9a"
TEXT_PRIMARY = "#1d1d1f"
TEXT_BODY = "#3a3a3c"
TEXT_MUTED = "#86868b"
TEXT_FAINT = "#aeaeb2"
OK_BG = "#e6f7f0"
OK_FG = "#1fae7a"
SOFT_BG = "#fff5f8"
TINT_BG = "#fff0f5"

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
_base_cache = None


def load_base():
    global _base_cache
    if _base_cache is None:
        with open(os.path.join(TEMPLATES_DIR, "base.html"), "r", encoding="utf-8") as f:
            _base_cache = f.read()
    return _base_cache


def esc(text):
    return html_lib.escape(str(text))


def esc_br(text):
    return html_lib.escape(str(text)).replace("\n", "<br />")


def emphasis(text):
    return f'<span style="color:{ACCENT_DARK}; font-weight:700;">{esc(text)}</span>'


def wrap(title, preheader, content):
    return (
        load_base()
        .replace("{{TITLE}}", esc(title))
        .replace("{{PREHEADER}}", esc(preheader))
        .replace("{{CONTENT}}", content)
    )


def cover_row(cover_url):
    return (
        '<tr><td style="padding:0; line-height:0;">'
        f'<img src="{esc(cover_url)}" width="600" alt="封面"'
        ' style="width:100%; max-width:600px; height:auto; max-height:260px;'
        ' object-fit:cover; display:block; border:0;" />'
        "</td></tr>"
    )


def badge_row(text, ok=True):
    bg, fg = (OK_BG, OK_FG) if ok else ("#fde8f0", ACCENT_DARK)
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:32px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td bgcolor="{bg}" style="background-color:{bg}; border-radius:999px;'
        f' padding:7px 18px; font-family:{FONT}; font-size:13px; font-weight:700;'
        f' color:{fg}; letter-spacing:0.01em;">' + esc(text) + "</td></tr>"
        "</table></td></tr>"
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
        f' line-height:1.15; font-weight:700; letter-spacing:-0.02em; color:{TEXT_PRIMARY};">'
        + esc(title)
        + "</h1></td></tr>"
    )


def paragraph_row(text, top=14):
    return (
        '<tr><td class="px content-bg"'
        f' style="padding:{top}px 48px 0 48px; background-color:#ffffff;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:15px;'
        f' line-height:1.75; color:{TEXT_BODY}; letter-spacing:0;">'
        + esc_br(text)
        + "</p></td></tr>"
    )


def card_row(label, content, mono=False):
    font = MONO if mono else FONT
    size = "13px" if mono else "15px"
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:22px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' style="background-color:{SOFT_BG}; border-radius:12px;'
        f' border-left:3px solid {ACCENT};">'
        '<tr><td style="padding:16px 20px;">'
        f'<div style="font-family:{FONT}; font-size:12px; font-weight:700;'
        f' color:{TEXT_MUTED}; letter-spacing:0.04em; padding-bottom:8px;">'
        + esc(label)
        + "</div>"
        f'<div style="font-family:{font}; font-size:{size}; line-height:1.7;'
        f' color:{TEXT_BODY}; word-break:break-word;">'
        + esc_br(content)
        + "</div>"
        "</td></tr></table></td></tr>"
    )


def id_row(label, value):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:18px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="font-family:{FONT}; font-size:13px; color:{TEXT_MUTED};'
        ' padding-right:10px;">' + esc(label) + "</td>"
        f'<td bgcolor="#fde8f0" style="background-color:#fde8f0; border-radius:8px;'
        f' padding:5px 14px; font-family:{MONO}; font-size:15px; font-weight:700;'
        f' color:{ACCENT_DARK}; letter-spacing:0.06em;">' + esc(value) + "</td>"
        "</tr></table></td></tr>"
    )


def highlight_row(text):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:20px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' style="background-color:{OK_BG}; border-radius:12px;">'
        f'<tr><td style="padding:16px 20px; font-family:{FONT}; font-size:14px;'
        f' line-height:1.7; color:{OK_FG}; font-weight:600;">'
        + esc(text)
        + "</td></tr></table></td></tr>"
    )


def hint_row(html_text):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:20px 48px 0 48px; background-color:#ffffff;">'
        f'<p style="margin:0; padding:14px 18px; background-color:{TINT_BG};'
        f' border-radius:10px; font-family:{FONT}; font-size:12px;'
        f' line-height:20px; color:{TEXT_MUTED};">'
        + html_text
        + "</p></td></tr>"
    )


def closing_row():
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:26px 48px 40px 48px; background-color:#ffffff;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:14px;'
        f' line-height:24px; color:{TEXT_MUTED};">此致</p>'
        f'<p style="margin:4px 0 0 0; font-family:{FONT}; font-size:15px;'
        f' font-weight:700; color:{TEXT_PRIMARY};">AiriCore Dev.</p></td></tr>'
    )


def contact_tip_row():
    return (
        '<tr><td class="px" style="padding:24px 48px 18px 48px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td style="background-color:{TINT_BG}; border-radius:10px;'
        ' padding:14px 18px;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:13px;'
        f' color:{TEXT_BODY}; line-height:20px; letter-spacing:0.005em;">'
        "建议将本邮件发件人添加到联系人，确保后续通知能正常送达收件箱。"
        "</p></td></tr></table></td></tr>"
    )


def unsubscribe_row(unsubscribe_url):
    return (
        '<tr><td style="padding:8px 48px 32px 48px; text-align:center;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="border-top:1px solid #f2f2f7; padding-top:22px;'
        ' text-align:center;">'
        '<table role="presentation" cellpadding="0" cellspacing="0"'
        ' style="margin:0 auto 10px auto;">'
        "<tr>"
        f'<td style="border:1px solid {ACCENT}; border-radius:7px; padding:9px 24px;'
        f' background-color:{SOFT_BG};">'
        f'<a href="{esc(unsubscribe_url)}"'
        f' style="font-family:{FONT}; font-size:13px; color:{TEXT_BODY};'
        ' text-decoration:none; display:block; white-space:nowrap;'
        ' letter-spacing:0.005em;">退订此类邮件</a>'
        "</td></tr></table>"
        f'<p style="margin:0; font-family:{FONT}; font-size:11px;'
        f' color:{TEXT_FAINT}; line-height:18px; letter-spacing:0.01em;">'
        "点击退订后将不再收到此类邮件，操作即时生效。"
        "</p></td></tr></table></td></tr>"
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


def article_body_row(html_content):
    body_style = (
        f"font-family:{FONT}; font-size:15px; line-height:1.75;"
        f" color:{TEXT_BODY}; letter-spacing:0;"
    )
    return (
        '<tr><td class="px content-bg" style="padding:18px 48px 36px 48px;'
        ' background-color:#ffffff;">'
        + _ARTICLE_CSS
        + f'<div class="article-body" style="{body_style}">'
        + html_content
        + "</div></td></tr>"
    )

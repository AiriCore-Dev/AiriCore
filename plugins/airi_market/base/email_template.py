import os
import html as html_lib

from . import state

FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"
_base_cache = None


def _load_base():
    global _base_cache
    if _base_cache is None:
        path = os.path.join(state.TEMPLATES_DIR, "base.html")
        with open(path, "r", encoding="utf-8") as f:
            _base_cache = f.read()
    return _base_cache


def _esc(t):
    return html_lib.escape(str(t))


def _wrap(title, preheader, content):
    return (
        _load_base()
        .replace("{{TITLE}}", _esc(title))
        .replace("{{PREHEADER}}", _esc(preheader))
        .replace("{{CONTENT}}", content)
    )


def _cover_row(cover_url):
    return (
        '<tr><td style="padding:0; line-height:0;">'
        f'<img src="{_esc(cover_url)}" width="600" alt="封面"'
        ' style="width:100%; max-width:600px; height:auto; max-height:260px;'
        ' object-fit:cover; display:block; border:0;" />'
        "</td></tr>"
    )


def _greeting_row(qq):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:32px 48px 0 48px; background-color:#ffffff;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:13px;'
        ' line-height:20px; color:#86868b; letter-spacing:0.01em;">'
        + _esc(f"致：{qq}@qq.com")
        + "</p></td></tr>"
    )


def _title_row(title):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:12px 48px 10px 48px; background-color:#ffffff;">'
        '<h1 class="h1"'
        f' style="margin:0; padding:0; font-family:{FONT}; font-size:26px;'
        ' line-height:1.15; font-weight:700; letter-spacing:-0.02em; color:#1d1d1f;">'
        + _esc(title)
        + "</h1></td></tr>"
    )


def _body_row(html_content):
    body_style = (
        f"font-family:{FONT}; font-size:15px; line-height:1.75;"
        " color:#3a3a3c; letter-spacing:0;"
    )
    inner = (
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
        f'<div class="article-body" style="{body_style}">'
        + html_content
        + "</div>"
    )
    return (
        '<tr><td class="px content-bg" style="padding:18px 48px 36px 48px;'
        ' background-color:#ffffff;">'
        + inner
        + "</td></tr>"
    )


def _contact_tip_row():
    return (
        '<tr><td class="px" style="padding:0 48px 18px 48px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="background-color:#fff0f5; border-radius:10px;'
        ' padding:14px 18px;">'
        f'<p style="margin:0; font-family:{FONT}; font-size:13px;'
        ' color:#3a3a3c; line-height:20px; letter-spacing:0.005em;">'
        "建议将本邮件发件人添加到联系人，确保后续通知能正常送达收件箱。"
        "</p>"
        "</td></tr>"
        "</table>"
        "</td></tr>"
    )


def _unsub_row(unsubscribe_url):
    return (
        '<tr><td style="padding:8px 48px 32px 48px; text-align:center;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="border-top:1px solid #f2f2f7; padding-top:22px;'
        ' text-align:center;">'
        '<table role="presentation" cellpadding="0" cellspacing="0"'
        ' style="margin:0 auto 10px auto;">'
        "<tr>"
        '<td style="border:1px solid #ffaacc; border-radius:7px; padding:9px 24px;'
        ' background-color:#fff5f8;">'
        f'<a href="{_esc(unsubscribe_url)}"'
        f' style="font-family:{FONT}; font-size:13px; color:#3a3a3c;'
        ' text-decoration:none; display:block; white-space:nowrap;'
        ' letter-spacing:0.005em;">退订此类邮件</a>'
        "</td>"
        "</tr>"
        "</table>"
        f'<p style="margin:0; font-family:{FONT}; font-size:11px;'
        ' color:#aeaeb2; line-height:18px; letter-spacing:0.01em;">'
        "点击退订后将不再收到此类邮件，操作即时生效。"
        "</p>"
        "</td></tr>"
        "</table>"
        "</td></tr>"
    )


def render_marketing_email(article_info, qq, unsubscribe_url):
    title = article_info["title"]
    cover_url = article_info.get("cover_url", "")
    html_content = article_info.get("html_content", "")

    rows = ""
    if cover_url:
        rows += _cover_row(cover_url)
    rows += _greeting_row(qq)
    rows += _title_row(title)
    rows += _body_row(html_content)
    rows += _contact_tip_row()
    rows += _unsub_row(unsubscribe_url)

    subject = title
    plain = (
        f"{title}\n\n"
        "（此邮件包含 HTML 格式内容，请使用支持 HTML 的邮件客户端查看）\n\n"
        f"退订请访问：{unsubscribe_url}\n\n"
        "此致，\nAiriCore Dev."
    )

    return subject, plain, _wrap(title, title, rows)


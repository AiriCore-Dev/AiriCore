import html

from utils.email import load_base

FONT = "-apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "'Menlo', 'Courier New', monospace"
ACCENT = "#ffaacc"
ACCENT_DARK = "#e85d9a"
TEXT_PRIMARY = "#1d1d1f"
TEXT_BODY = "#3a3a3c"
TEXT_MUTED = "#86868b"
OK_BG = "#e6f7f0"
OK_FG = "#1fae7a"
SOFT_BG = "#fff5f8"
TINT_BG = "#fff0f5"


def esc(text):
    return html.escape(str(text))


def wrap(title, preheader, content):
    return load_base().replace("{{TITLE}}", esc(title)).replace("{{PREHEADER}}", esc(preheader)).replace("{{CONTENT}}", content)


def emphasis(text):
    return f'<span style="color:{ACCENT_DARK}; font-weight:700;">{esc(text)}</span>'


def _text(text):
    return esc(text).replace("\n", "<br />")


def badge_row(text, ok=True):
    bg, fg = (OK_BG, OK_FG) if ok else ("#fde8f0", ACCENT_DARK)
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:32px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td bgcolor="{bg}" style="background-color:{bg}; border-radius:999px;'
        f' padding:7px 18px; font-family:{FONT}; font-size:13px; font-weight:700;'
        f' color:{fg}; letter-spacing:0.01em;">'
        + esc(text)
        + "</td></tr></table></td></tr>"
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
        + _text(text)
        + "</p></td></tr>"
    )


def card_row(label, content, mono=False):
    font = MONO if mono else FONT
    size = "13px" if mono else "15px"
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:22px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' style="background-color:{SOFT_BG}; border-radius:12px; border-left:3px solid {ACCENT};">'
        '<tr><td style="padding:16px 20px;">'
        f'<div style="font-family:{FONT}; font-size:12px; font-weight:700;'
        f' color:{TEXT_MUTED}; letter-spacing:0.04em; padding-bottom:8px;">'
        + esc(label)
        + "</div>"
        f'<div style="font-family:{font}; font-size:{size}; line-height:1.7;'
        f' color:{TEXT_BODY}; word-break:break-word;">'
        + _text(content)
        + "</div>"
        "</td></tr></table></td></tr>"
    )


def id_row(label, value):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:18px 48px 0 48px; background-color:#ffffff;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="font-family:{FONT}; font-size:13px; color:{TEXT_MUTED}; padding-right:10px;">'
        + esc(label)
        + "</td>"
        f'<td bgcolor="#fde8f0" style="background-color:#fde8f0; border-radius:8px;'
        f' padding:5px 14px; font-family:{MONO}; font-size:15px; font-weight:700;'
        f' color:{ACCENT_DARK}; letter-spacing:0.06em;">'
        + esc(value)
        + "</td></tr></table></td></tr>"
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


__all__ = [
    "badge_row",
    "card_row",
    "closing_row",
    "emphasis",
    "esc",
    "highlight_row",
    "hint_row",
    "id_row",
    "paragraph_row",
    "title_row",
    "wrap",
]

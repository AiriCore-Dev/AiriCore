from utils import email as et


def render_marketing_email(article_info, qq, unsubscribe_url):
    title = article_info["title"]
    cover_url = article_info.get("cover_url", "")
    html_content = article_info.get("html_content", "")

    rows = ""
    if cover_url:
        rows += et.cover_row(cover_url)
    rows += et.note_row(f"致：{qq}@qq.com")
    rows += et.title_row(title)
    rows += et.article_body_row(html_content)
    rows += et.contact_tip_row()
    rows += et.unsubscribe_row(unsubscribe_url)

    subject = title
    plain = (
        f"{title}\n\n"
        "（此邮件包含 HTML 格式内容，请使用支持 HTML 的邮件客户端查看）\n\n"
        f"退订请访问：{unsubscribe_url}\n\n"
        "此致，\nAiriCore Dev."
    )

    return subject, plain, et.wrap(title, title, rows)

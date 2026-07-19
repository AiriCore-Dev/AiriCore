import os
import re
import yaml
import markdown as md_lib
from pathlib import Path
import html as html_lib


SCRIPT_DIR = Path(__file__).parent
POSTS_DIR = SCRIPT_DIR / "posts"
TEMPLATES_DIR = SCRIPT_DIR / "templates"
FONT = "'Segoe UI', Arial, sans-serif"


def _esc(t):
    return html_lib.escape(str(t))


def _load_base():
    path = TEMPLATES_DIR / "base.html"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
        ' style="width:100%; max-width:600px; height:auto; max-height:280px;'
        ' object-fit:cover; display:block; border:0;" />'
        "</td></tr>"
    )


def _title_row(title):
    return (
        '<tr><td class="px content-bg"'
        ' style="padding:36px 40px 8px 40px; background-color:#ffffff;">'
        '<h1 class="h1 text-primary"'
        f' style="margin:0; padding:0; font-family:{FONT}; font-size:26px;'
        ' line-height:36px; font-weight:700; color:#2b2b33;">'
        + _esc(title)
        + "</h1></td></tr>"
    )


def _body_row(html_content):
    body_style = (
        f"font-family:{FONT}; font-size:15px; line-height:1.8; color:#44444f;"
    )
    inner = (
        "<style>"
        ".article-body h2{font-size:18px;font-weight:700;color:#2b2b33;"
        "border-bottom:2px solid #ffaad4;padding-bottom:6px;margin:1.4em 0 .6em 0;}"
        ".article-body h3{font-size:16px;font-weight:700;color:#2b2b33;margin:1.2em 0 .5em 0;}"
        ".article-body img{max-width:100%;height:auto;border-radius:10px;"
        "margin:12px 0;display:block;}"
        ".article-body a{color:#e85d9a;text-decoration:none;}"
        ".article-body blockquote{margin:16px 0;padding:14px 20px;"
        "background:#fdf5f9;border-left:4px solid #ffaad4;"
        "border-radius:0 8px 8px 0;color:#55555f;font-style:italic;}"
        ".article-body code{background:#f5f0f7;padding:2px 6px;border-radius:4px;"
        "font-family:'JetBrains Mono',Consolas,monospace;font-size:13px;color:#c7254e;}"
        ".article-body pre{background:#f5f0f7;padding:16px;border-radius:10px;overflow-x:auto;}"
        ".article-body pre code{background:none;padding:0;color:#2b2b33;font-size:13px;}"
        ".article-body table{width:100%;border-collapse:collapse;margin:16px 0;}"
        ".article-body th{background:#fdf5f9;color:#2b2b33;font-weight:700;"
        "padding:10px 14px;border:1px solid #f0d8e8;}"
        ".article-body td{padding:9px 14px;border:1px solid #f0d8e8;color:#44444f;}"
        ".article-body hr{border:none;border-top:2px solid #f0d8e8;margin:24px 0;}"
        "@media(prefers-color-scheme:dark){"
        ".article-body{color:#c8c8d8;}"
        ".article-body h2,.article-body h3{color:#f0f0f5;}"
        ".article-body blockquote{background:#2e2e3a;color:#a8a8b8;}"
        ".article-body code{background:#2e2e3a;color:#ff9ec8;}"
        ".article-body pre{background:#2e2e3a;}"
        ".article-body pre code{color:#c8c8d8;}"
        ".article-body th{background:#2e2e3a;color:#f0f0f5;border-color:#3e3e4e;}"
        ".article-body td{border-color:#3e3e4e;color:#c8c8d8;}"
        ".article-body hr{border-top-color:#3e3e4e;}"
        "}"
        "</style>"
        f'<div class="article-body" style="{body_style}">'
        + html_content
        + "</div>"
    )
    return (
        '<tr><td class="px" style="padding:16px 40px 32px 40px;">'
        + inner
        + "</td></tr>"
    )


def _unsub_row(unsubscribe_url):
    return (
        '<tr><td class="px" style="padding:0 40px 28px 40px;">'
        '<p style="margin:0; font-family:'
        + FONT
        + '; font-size:12px; line-height:20px; color:#b0b0ba; text-align:center;">'
        '如不希望再收到此类邮件，请 '
        f'<a href="{_esc(unsubscribe_url)}"'
        ' style="color:#b0b0ba; text-decoration:underline;">点击此处退订</a>'
        "</p></td></tr>"
    )


def render_marketing_email(article_info, unsubscribe_url):
    title = article_info["title"]
    cover_url = article_info.get("cover_url", "")
    html_content = article_info.get("html_content", "")

    rows = ""
    if cover_url:
        rows += _cover_row(cover_url)
    rows += _title_row(title)
    rows += _body_row(html_content)
    rows += _unsub_row(unsubscribe_url)

    return _wrap(title, title, rows)


def image_url(article_name, filename):
    return f"./{article_name}/{filename}"


def parse_article(article_name):
    article_dir = POSTS_DIR / article_name
    index_path = article_dir / "index.md"

    with open(index_path, "r", encoding="utf-8") as f:
        raw = f.read()

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except Exception:
            fm = {}
        body = raw[fm_match.end():]
    else:
        fm = {}
        body = raw

    title = fm.get("title", article_name)
    cover = fm.get("cover", "")

    def _replace_img(m):
        alt = m.group(1)
        src = m.group(2)
        if not src.startswith("http"):
            src = image_url(article_name, src)
        return f"![{alt}]({src})"

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace_img, body)

    html_content = md_lib.markdown(
        body,
        extensions=["extra", "nl2br"],
        output_format="html",
    )

    cover_url = image_url(article_name, cover) if cover else ""

    return {
        "title": title,
        "cover_url": cover_url,
        "html_content": html_content,
    }


def list_articles():
    if not POSTS_DIR.is_dir():
        return []
    return [
        d.name for d in POSTS_DIR.iterdir()
        if d.is_dir() and (d / "index.md").is_file()
    ]


def render_all_posts(output_dir: str = "/Users/liko/Downloads/airi_market_html"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    articles = list_articles()

    if not articles:
        print("未找到文章")
        return

    print(f"找到 {len(articles)} 篇文章，开始渲染...")

    for article_name in articles:
        try:
            article_info = parse_article(article_name)
            dummy_unsub = "https://example.com/unsubscribe?token=dummy"
            html_body = render_marketing_email(article_info, dummy_unsub)

            html_file = output_path / f"{article_name}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_body)

            print(f"OK {article_name} -> {html_file}")

        except Exception as e:
            print(f"FAIL {article_name} 渲染失败: {e}")

    print(f"\n完成！输出目录: {output_path}")


if __name__ == "__main__":
    render_all_posts()

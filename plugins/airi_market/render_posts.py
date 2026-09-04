import re
import sys
import yaml
import markdown as md_lib
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
POSTS_DIR = SCRIPT_DIR / "posts"
_ROOT_DIR = SCRIPT_DIR.parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from .base import email_components as et


def render_marketing_email(article_info, unsubscribe_url):
    title = article_info["title"]
    cover_url = article_info.get("cover_url", "")
    html_content = article_info.get("html_content", "")

    rows = ""
    if cover_url:
        rows += et.cover_row(cover_url)
    rows += et.title_row(title, top=32)
    rows += et.article_body_row(html_content)
    rows += et.contact_tip_row()
    rows += et.unsubscribe_row(unsubscribe_url)

    return et.wrap(title, title, rows)


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


def render_all_posts(output_dir="output/airi_market_html"):
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

    print(f"完成，输出目录: {output_path}")


if __name__ == "__main__":
    render_all_posts()

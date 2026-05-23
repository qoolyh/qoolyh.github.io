#!/usr/bin/env python3
import os
import requests

# --- 配置区 ---
ORCID_ID = "0000-0003-1808-9579"  # 记得改成你自己的 ORCID ID
OUTPUT_DIR = "_publications"
MAX_PAPERS = 15  # 可以多抓几篇，防止有的因为数据不全被跳过


# ----------

def sanitize_filename(title):
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title).rstrip()


def safe_get(data, *keys, default=None):
    """
    安全地获取嵌套字典的值，防止 NoneType 报错
    """
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, AttributeError):
            return default
    return data if data is not None else default


def extract_work_info(work_summary):
    try:
        # 1. 提取标题 (加强保护)
        title = safe_get(work_summary, "title", "title", "value", default="").strip()
        if not title:
            print("   ⚠️ 标题为空，跳过")
            return None

        # 2. 提取年份 (加强保护)
        year_val = safe_get(work_summary, "publication-date", "year", "value", default=None)
        if year_val:
            year_str = str(year_val)
        else:
            # 如果年份真的没有，尝试从其他字段猜，或者给个默认
            print(f"   ⚠️ 未找到年份，默认为 1900: {title}")
            year_str = "1900"

        # 3. 提取期刊/类型
        journal = safe_get(work_summary, "journal-title", "value", default="").strip()
        if not journal:
            work_type = safe_get(work_summary, "type", default="").lower()
            journal = "Preprint" if "preprint" in work_type else "Conference/Journal"

        # 4. 提取 URL/DOI
        url = "#"
        external_ids = safe_get(work_summary, "external-ids", "external-id", default=[])
        for ext_id in external_ids:
            id_type = safe_get(ext_id, "external-id-type", default="")
            id_value = safe_get(ext_id, "external-id-value", default="")
            if id_type == "doi" and id_value:
                url = f"https://doi.org/{id_value}"
                break
            elif id_type == "uri" and id_value:
                url = id_value

        # 5. 提取作者 (取前3个)
        contributors_list = safe_get(work_summary, "contributors", "contributor", default=[])
        authors = []
        for contrib in contributors_list[:3]:
            name = safe_get(contrib, "credit-name", "value", default="").strip()
            if name:
                authors.append(name)

        if not authors:
            author_str = "Unknown Author"
        else:
            author_str = "; ".join(authors) + (" et al." if len(contributors_list) > 3 else "")

        # 6. 摘要
        abstract = safe_get(work_summary, "short-description", default="No abstract available.").strip()

        return {
            "title": title,
            "year": year_str,
            "journal": journal,
            "url": url,
            "author_str": author_str,
            "abstract": abstract
        }

    except Exception as e:
        print(f"   ❌ 解析出错: {e}")
        return None


def generate_jekyll_markdown(work_info):
    title = work_info["title"]
    year = work_info["year"]
    journal = work_info["journal"]
    url = work_info["url"]
    author_str = work_info["author_str"]
    abstract = work_info["abstract"]

    # 文件名
    filename = f"{year}-{sanitize_filename(title)[:50].replace(' ', '-').lower()}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"   ⏭️ 跳过已存在: {filename}")
        return False

    content = f"""---
title: "{title}"
collection: publications
permalink: /publication/{filename.replace('.md', '')}
excerpt: '{abstract[:150]}...'
date: {year}-01-01
venue: '{journal}'
paperurl: '{url}'
citation: '{author_str} ({year}). {title}. <i>{journal}</i>.'
---
{abstract}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ 生成: {filename}")
    return True


def main():
    print(f"🚀 开始从 ORCID {ORCID_ID} 获取论文...")

    api_url = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ API 请求失败: {e}")
        return

    works_groups = data.get("group", [])
    print(f"📚 共找到 {len(works_groups)} 篇论文，处理前 {MAX_PAPERS} 篇...\n")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    count = 0
    for i, group in enumerate(works_groups[:MAX_PAPERS]):
        work_summaries = group.get("work-summary", [])
        if not work_summaries:
            continue

        work_summary = work_summaries[0]
        display_title = safe_get(work_summary, "title", "title", "value", default="未知标题")
        print(f"🔍 [{i + 1}/{MAX_PAPERS}] 处理: {display_title}")

        work_info = extract_work_info(work_summary)
        if not work_info:
            continue

        if generate_jekyll_markdown(work_info):
            count += 1

    print(f"\n🎉 完成！本次新增 {count} 篇论文。")


if __name__ == "__main__":
    main()

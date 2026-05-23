#!/usr/bin/env python3
import os
import requests
import time

# --- 配置区 ---
ORCID_ID = "0000-0003-1808-9579"  # 你的ORCID ID
OUTPUT_DIR = "_publications"
MAX_PAPERS = 15


# ----------

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
    #print(f"   ✅ 生成: {filename}")
    return True


def sanitize_filename(title):
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title).rstrip()


def safe_get(data, *keys, default=None):
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, AttributeError):
            return default
    return data if data is not None else default


def get_work_details(put_code):
    """获取单篇论文的详细信息（含作者）"""
    # 构造详情页 API 地址
    detail_url = f"https://pub.orcid.org/v3.0/{ORCID_ID}/work/{put_code}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(detail_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"      ⚠️ 获取详情失败，状态码: {response.status_code}")
            return None
    except Exception as e:
        print(f"      ❌ 请求详情异常: {e}")
        return None


def extract_work_info(work_summary):
    try:
        put_code = safe_get(work_summary, "put-code", default=None)
        title = safe_get(work_summary, "title", "title", "value", default="").strip()
        if not title:
            return None

        # 基础信息提取
        year_val = safe_get(work_summary, "publication-date", "year", "value", default=None)
        year_str = str(year_val) if year_val else "1900"
        journal = safe_get(work_summary, "journal-title", "value", default="").strip()
        if not journal:
            work_type = safe_get(work_summary, "type", default="").lower()
            journal = "Preprint" if "preprint" in work_type else "Conference/Journal"

        url = "#"
        external_ids = safe_get(work_summary, "external-ids", "external-id", default=[])
        for ext_id in external_ids:
            if safe_get(ext_id, "external-id-type") == "doi":
                url = f"https://doi.org/{safe_get(ext_id, 'external-id-value')}"
                break

        # --- 关键步骤：获取作者 ---
        # 1. 先尝试从 summary 拿（可能没有）
        contributors_list = safe_get(work_summary, "contributors", "contributor", default=[])

        # 2. 如果没有作者，且我们有 put-code，就去请求详情接口
        if not contributors_list and put_code:
            print(f"      ℹ️ Summary 无作者，正在请求详情接口...")
            detail_data = get_work_details(put_code)
            if detail_data:
                contributors_list = safe_get(detail_data, "contributors", "contributor", default=[])
                # 详情接口也可能没有，那就算了
                if not contributors_list:
                    print(f"      ⚠️ 详情接口也未包含作者信息")

        # 3. 格式化作者字符串
        authors = []
        if contributors_list:
            for contrib in contributors_list[:5]:  # 取前5个
                name = safe_get(contrib, "credit-name", "value", default="").strip()
                if name:
                    authors.append(name)

        if authors:
            author_str = "; ".join(authors) + (" et al." if len(contributors_list) > 5 else "")
        else:
            author_str = "Unknown Author"  # 实在没有就用 Unknown

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
        print(f"🔍 [{i + 1}/{MAX_PAPERS}] {display_title}")

        work_info = extract_work_info(work_summary)
        if not work_info:
            continue

        # 生成 Markdown (复用你之前的 generate_jekyll_markdown 函数)
        if generate_jekyll_markdown(work_info):
            count += 1

        # 礼貌性延迟，防止被 ORCID 限流
        time.sleep(1)

    print(f"\n🎉 完成！本次新增 {count} 篇论文。")


if __name__ == "__main__":
    main()

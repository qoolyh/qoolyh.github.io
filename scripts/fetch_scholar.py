#!/usr/bin/env python3
import os
import re

import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 配置区 ---
ORCID_ID = "0000-0003-1808-9579"  # 你的ORCID ID
OUTPUT_DIR = "_publications"
MAX_PAPERS = 20


# ----------
def fetch_abstract_from_crossref(doi, session):
    """通过 DOI 去 Crossref API 拉取摘要 (修复 dict 报错)"""
    if not doi:
        return ""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        r = session.get(url, timeout=10)
        if r.status_code != 200:
            return ""

        data = r.json()
        msg = data.get("message", {})

        # 1. 获取 raw_abstract
        raw_abs = msg.get("abstract")

        # 2. 关键修复：判断类型
        abstract_text = ""
        if isinstance(raw_abs, dict):
            # 如果是字典，通常摘要存在 '#text' 键里
            abstract_text = raw_abs.get("#text", "")
        elif isinstance(raw_abs, str):
            # 如果是字符串，直接用
            abstract_text = raw_abs
        else:
            return ""  # 其他情况返回空

        # 3. 清理 HTML 标签
        if abstract_text:
            # 移除 HTML 标签
            clean_text = re.sub(r'<[^>]+>', '', abstract_text).strip()
            # 移除多余的空白符
            clean_text = re.sub(r'\s+', ' ', clean_text)
            if len(clean_text) > 20:
                return clean_text

        return ""
    except Exception as e:
        print(f"      ⚠️ Crossref 拉摘要失败: {e}")
        return ""


def generate_jekyll_markdown(work_info):
    """严格按照 Academic Pages 例子格式生成 Markdown"""
    title = work_info["title"]
    year = work_info["year"]
    month = work_info.get("month", "01")  # 如果有月份用月份，没有默认01
    day = work_info.get("day", "01")  # 如果有日期用日期，没有默认01

    journal = work_info["journal"]
    url = work_info["url"]
    author_str = work_info["author_str"]
    abstract = work_info["abstract"]

    # 1. 文件名处理：年-月-日-标题
    # 确保日期是 YYYY-MM-DD 格式
    date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # 生成文件名 (slug)
    slug = sanitize_filename(title)[:50].replace(' ', '-').lower()
    filename = f"{date_str}-{slug}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"   ⏭️ 跳过已存在: {filename}")
        return False

    # 2. 关键：清理摘要和引用中的特殊字符，防止 YAML 解析失败
    # 把双引号替换成 HTML实体 &quot; 或者中文引号，这里用单引号包裹整个字段
    clean_abstract = abstract.replace('"', '').replace("'", "").replace(":", " -").strip()
    clean_journal = journal.replace('"', '').replace("'", "")

    # 构造 Citation (模仿你的例子，使用 &quot; 转义引号)
    # 注意：例子里的 &quot; 是为了在 HTML 里显示引号，YAML 里我们用单引号包裹就行
    citation_text = f'{author_str} ({year}). "{title}". <i>{clean_journal}</i>.'

    # 3. 严格按照你提供的模板格式生成
    # 注意：这里使用 | 符号表示保留换行，或者直接用字符串拼接
    content = f"""---
title: "{title}"
collection: publications
category: manuscripts
permalink: /publication/{date_str}-{slug}
excerpt: '{clean_abstract[:150]}...'
date: {date_str}
venue: '{clean_journal}'
paperurl: '{url}'
citation: '{citation_text}'
---

{abstract}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ 生成: {filename}")
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


def extract_work_info(work_summary, session=None):
    try:
        put_code = safe_get(work_summary, "put-code", default=None)
        title = safe_get(work_summary, "title", "title", "value", default="").strip()
        if not title:
            return None

        # ---- 基础字段（从 summary 拿）----
        year_val = safe_get(work_summary, "publication-date", "year", "value", default=None)
        month_val = safe_get(work_summary, "publication-date", "month", "value", default="01")
        day_val = safe_get(work_summary, "publication-date", "day", "value", default="01")
        year_str = str(year_val) if year_val else "1900"
        month_str = str(month_val).zfill(2)
        day_str = str(day_val).zfill(2)

        journal = safe_get(work_summary, "journal-title", "value", default="").strip()
        if not journal:
            work_type = safe_get(work_summary, "type", default="").lower()
            journal = "Preprint" if "preprint" in work_type else "Conference/Journal"

        # DOI 提取
        doi = None
        url = "#"
        external_ids = safe_get(work_summary, "external-ids", "external-id", default=[])
        for ext_id in external_ids:
            if safe_get(ext_id, "external-id-type") == "doi":
                doi = safe_get(ext_id, "external-id-value", default="")
                url = f"https://doi.org/{doi}"
                break

        # ---- Step 1: 拿详情接口（作者 + ORCID 自带 description）----
        contributors_list = safe_get(work_summary, "contributors", "contributor", default=[])
        orcid_description = ""

        if put_code:
            detail_data = get_work_details(put_code)
            if detail_data:
                # 作者（如果 summary 没有）
                if not contributors_list:
                    contributors_list = safe_get(detail_data, "contributors", "contributor", default=[])
                # ORCID 自带的 description
                orcid_description = safe_get(detail_data, "short-description", default="") or \
                                    safe_get(detail_data, "description", default="")

        # ---- Step 2: 摘要策略 ----
        # 优先用 ORCID 存的 description，没有就去 Crossref 查
        abstract = ""
        if orcid_description and len(orcid_description.strip()) > 20:
            abstract = orcid_description.strip()
        elif doi and session:
            print("wow! \n")
            abstract = fetch_abstract_from_crossref(doi, session)

        if not abstract:
            abstract = "No abstract available."

        # ---- Step 3: 作者格式化 ----
        authors = []
        if contributors_list:
            for contrib in contributors_list[:5]:
                name = safe_get(contrib, "credit-name", "value", default="").strip()
                if name:
                    authors.append(name)
        author_str = "; ".join(authors) + (" et al." if len(contributors_list) > 5 else "") if authors else "Unknown Author"

        return {
            "title": title,
            "year": year_str,
            "month": month_str,
            "day": day_str,
            "journal": journal,
            "url": url,
            "doi": doi,
            "author_str": author_str,
            "abstract": abstract
        }

    except Exception as e:
        print(f"   ❌ 解析出错: {e}")
        return None


# ----------

# ... (保留 sanitize_filename, safe_get, get_work_details, extract_work_info, generate_jekyll_markdown 函数) ...

def main():
    print(f"🚀 开始从 ORCID {ORCID_ID} 获取论文...")

    # 1. 配置 Session，禁用代理，增加重试
    session = requests.Session()

    # 关键：强制不走代理（解决 ProxyError）
    session.trust_env = False

    # 配置重试策略
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {"Accept": "application/json"}
    api_url = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"

    try:
        # 使用 session 发送请求
        response = session.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.ProxyError:
        print("❌ 严重错误：检测到代理错误。已尝试禁用代理，请检查 GitHub Actions 网络环境。")
        return
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
        print(work_summaries)
        work_summary = work_summaries[0]
        display_title = safe_get(work_summary, "title", "title", "value", default="未知标题")
        print(f"🔍 [{i + 1}/{MAX_PAPERS}] {display_title}")

        work_info = extract_work_info(work_summary,session)
        if not work_info:
            continue

        if generate_jekyll_markdown(work_info):
            count += 1

        time.sleep(1)

    print(f"\n🎉 完成！本次新增 {count} 篇论文。")


if __name__ == "__main__":
    main()

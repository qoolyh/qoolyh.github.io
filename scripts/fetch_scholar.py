#!/usr/bin/env python3
import os
import requests
from datetime import datetime

# --- 1. 配置区：填入你自己的 ORCID ID ---
ORCID_ID = "0000-0003-1808-9579"  # <--- 改成你自己的 ORCID ID
OUTPUT_DIR = "_publications"
MAX_PAPERS = 10
# ---------------------------------------

def sanitize_filename(title):
    """清理文件名，移除特殊字符"""
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title).rstrip()

def generate_jekyll_markdown(work):
    """将 ORCID 的论文数据转换为 Academic Pages 的 Markdown 格式"""
    try:
        # 提取基本信息
        title = work.get('title', {}).get('title', {}).get('value', 'No Title')
        
        # 提取年份
        year_str = None
        if work.get('publication-date') and work['publication-date'].get('year'):
            year_str = str(work['publication-date']['year']['value'])
        else:
            year_str = "1900" # 如果没有年份，默认一个
        
        # 构建日期字符串
        date_str = f"{year_str}-01-01"
        
        # 提取期刊/会议名称
        journal = "N/A"
        if work.get('journal-title'):
            journal = work['journal-title'].get('value', 'N/A')
        
        # 提取作者列表
        authors = []
        for contrib in work.get('contributors', {}).get('contributor', []):
            if contrib.get('credit-name') and contrib['credit-name'].get('value'):
                authors.append(contrib['credit-name']['value'])
        author_str = ", ".join(authors) if authors else "Unknown Author"
        
        # 提取外部链接 (DOI 或 URL)
        ext_ids = work.get('external-ids', {}).get('external-id', [])
        url = "#"
        doi = None
        for ext_id in ext_ids:
            if ext_id.get('external-id-type') == 'doi':
                doi = ext_id.get('external-id-value')
                url = f"https://doi.org/{doi}"
                break
            elif ext_id.get('external-id-type') == 'uri':
                url = ext_id.get('external-id-value')
        
        # 提取摘要 (ORCID 的摘要通常在 here 或 summary 里，视具体情况而定)
        abstract = "No abstract available."
        # 尝试从 full-text 获取，如果是 None 则保持默认
        if work.get('short-description'):
            abstract = work['short-description']

        # 构建文件名
        filename = f"{year_str}-{sanitize_filename(title)[:50].replace(' ', '-').lower()}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # 检查文件是否已存在
        if os.path.exists(filepath):
            print(f"Skipping existing file: {filename}")
            return

        # Academic Pages 的 Front Matter 格式
        content = f"""---
title: "{title}"
collection: publications
permalink: /publication/{filename.replace('.md', '')}
excerpt: '{abstract[:150]}...'
date: {date_str}
venue: '{journal}'
paperurl: '{url}'
citation: '{author_str} ({year_str}). {title}. <i>{journal}</i>.'
---
{abstract}
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Generated: {filename}")
    except Exception as e:
        print(f"Error processing paper '{title}': {e}")

def main():
    print(f"Fetching publications for ORCID: {ORCID_ID}")
    
    # ORCID Public API v3.0 端点
    url = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"
    headers = {"Accept": "application/json"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching data from ORCID: {response.status_code}")
        return
        
    data = response.json()
    
    # 确保输出目录存在
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    works = data.get('group', [])
    # 按年份降序排列，确保最新的论文在前
    works.sort(key=lambda x: (
        x.get('work-summary', [{}])[0].get('publication-date', {}).get('year', {}).get('value', 0) 
        if x.get('work-summary') else 0
    ), reverse=True)

    count = 0
    for work_group in works[:MAX_PAPERS]:
        # 获取详细的 work 信息
        work_summary = work_group.get('work-summary', [{}])[0]
        work_url = work_summary.get('source') # 这个实际上是 /works/{put-code} 的相对路径
        
        if work_url:
            # 拼接获取单篇论文详情的 API 地址
            detail_url = f"https://pub.orcid.org/v3.0/{ORCID_ID}{work_url}"
            detail_response = requests.get(detail_url, headers=headers)
            
            if detail_response.status_code == 200:
                work_detail = detail_response.json()
                generate_jekyll_markdown(work_detail)
                count += 1
            else:
                print(f"Failed to fetch details for a paper. Status code: {detail_response.status_code}")

    print(f"Successfully generated {count} papers.")

if __name__ == "__main__":
    main()

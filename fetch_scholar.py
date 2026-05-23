import os
from scholarly import scholarly, ProxyGenerator
import time
from datetime import datetime

# --- 配置区 ---
# 请替换为你自己的 Google Scholar ID
AUTHOR_ID = "PF-BShoAAAAJ" 
# 生成的 Markdown 文件存放目录 (Academic Pages 标准目录)
OUTPUT_DIR = "_publications"
# 只更新最近 N 篇论文，防止重复生成旧文件
MAX_PAPERS = 10 
# --- 配置区结束 ---

def sanitize_filename(title):
    """清理文件名，移除特殊字符"""
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title).rstrip()

def generate_jekyll_markdown(pub):
    """
    将 scholarly 获取的 publication 对象转换为 Academic Pages 风格的 Markdown
    """
    # 提取信息
    title = pub.get('bib', {}).get('title', 'No Title')
    author = pub.get('bib', {}).get('author', 'Unknown Author')
    year = pub.get('bib', {}).get('year', 'N/A')
    journal = pub.get('bib', {}).get('journal', 'Preprint' if 'arxiv' in pub.get('pub_url', '').lower() else 'Conference/Journal')
    abstract = pub.get('bib', {}).get('abstract', '')
    
    # 构造 URL
    url = pub.get('pub_url', pub.get('eprint_url', '#'))
    
    # 生成文件名 (例如: 2023-05-12-awesome-paper.md)
    date_str = f"{year}-01-01" # 如果没有具体日期，默认年初一
    if len(date_str) != 10:
        date_str = f"{year}-01-01"
    
    filename = f"{date_str}-{sanitize_filename(title)[:50].replace(' ', '-').lower()}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 检查文件是否已存在，如果存在则跳过（简单逻辑，你也可以改为覆盖）
    if os.path.exists(filepath):
        print(f"Skipping existing file: {filename}")
        return

    # Academic Pages 的 Front Matter 格式
    content = f"""---
title: "{title}"
collection: publications
permalink: /publication/{filename.replace('.md', '')}
excerpt: '{abstract[:150]}...' # 摘要截取前150字
date: {date_str}
venue: '{journal}'
paperurl: '{url}'
citation: '{author}, et al. ({year}). {title}. <i>{journal}</i>.'
---
{abstract}
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Generated: {filename}")

def main():
    # 可选：设置代理，如果在 GitHub Actions 上跑，有时需要用代理才能访问 Scholar
    # pg = ProxyGenerator()
    # pg.FreeProxies()
    # scholarly.use_proxy(pg)
    
    print(f"Fetching author info for ID: {AUTHOR_ID}")
    
    try:
        author = scholarly.search_author_id(AUTHOR_ID)
        author = scholarly.fill(author, sections=['publications'])
        
        print(f"Author: {author.get('name')}")
        print(f"Total publications found: {len(author.get('publications', []))}")
        
        # 确保输出目录存在
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        count = 0
        # 遍历出版物，按年份排序通常最新的在最前面，但 scholarly 返回的不一定完全有序
        # 这里简单取前 MAX_PAPERS 个
        for pub in author.get('publications', [])[:MAX_PAPERS]:
            try:
                # 填充详细信息（包含摘要和链接）
                filled_pub = scholarly.fill(pub)
                generate_jekyll_markdown(filled_pub)
                count += 1
                # 礼貌性延迟，防止被封
                time.sleep(3) 
            except Exception as e:
                print(f"Error processing paper: {pub.get('bib', {}).get('title', 'N/A')}. Error: {e}")
                continue
                
        print(f"Successfully generated {count} new papers.")
        
    except Exception as e:
        print(f"Failed to fetch data from Google Scholar: {e}")
        # 在 GitHub Actions 中，如果是网络错误，最好退出码为 1 以便重试
        exit(1)

if __name__ == "__main__":
    main()

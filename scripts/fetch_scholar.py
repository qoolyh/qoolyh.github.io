#!/usr/bin/env python3
import os
import sys
import signal
from scholarly import scholarly
import time
import urllib.request

# --- 配置区 ---
AUTHOR_ID = "PF-BShoAAAAJ" 
OUTPUT_DIR = "_publications"
MAX_PAPERS = 10 
# --- 配置区结束 ---

# 1. 设置全局超时（防止网络请求无限等待）
def timeout_handler(signum, frame):
    raise TimeoutError("Network request timed out!")
signal.signal(signal.SIGALRM, timeout_handler)

def sanitize_filename(title):
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title).rstrip()

def generate_jekyll_markdown(pub):
    try:
        title = pub.get('bib', {}).get('title', 'No Title')
        author = pub.get('bib', {}).get('author', 'Unknown Author')
        year = pub.get('bib', {}).get('year', 'N/A')
        journal = pub.get('bib', {}).get('journal', 'Preprint' if 'arxiv' in str(pub.get('pub_url', '')).lower() else 'Conference/Journal')
        abstract = pub.get('bib', {}).get('abstract', '')
        url = pub.get('pub_url', pub.get('eprint_url', '#'))
        
        date_str = f"{year}-01-01"
        if len(date_str) != 10:
            date_str = f"{year}-01-01"
        
        filename = f"{date_str}-{sanitize_filename(title)[:50].replace(' ', '-').lower()}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            print(f"Skipping existing file: {filename}")
            return

        content = f"""---
title: "{title}"
collection: publications
permalink: /publication/{filename.replace('.md', '')}
excerpt: '{abstract[:150]}...'
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
    except Exception as e:
        print(f"Error writing file for {pub.get('bib', {}).get('title', 'N/A')}: {e}")

def main():
    print(f"Fetching author info for ID: {AUTHOR_ID}")
    
    # 2. 测试网络连通性（可选，帮助诊断）
    try:
        print("Testing network connection to Google...")
        urllib.request.urlopen('https://scholar.google.com', timeout=10)
        print("Network seems OK.")
    except Exception as e:
        print(f"Warning: Network test failed: {e}")

    try:
        # 3. 设置超时（例如 60 秒）
        signal.alarm(60) 
        
        print("Searching author...")
        author = scholarly.search_author_id(AUTHOR_ID)
        
        print("Filling author details...")
        author = scholarly.fill(author, sections=['publications'])
        
        signal.alarm(0) # 取消超时
        
        print(f"Author: {author.get('name')}")
        print(f"Total publications found: {len(author.get('publications', []))}")
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        count = 0
        for pub in author.get('publications', [])[:MAX_PAPERS]:
            try:
                # 每次请求也设个短超时
                signal.alarm(30)
                filled_pub = scholarly.fill(pub)
                signal.alarm(0)
                
                generate_jekyll_markdown(filled_pub)
                count += 1
                time.sleep(3) 
            except TimeoutError:
                print(f"Timeout processing paper: {pub.get('bib', {}).get('title', 'N/A')}. Skipping.")
                signal.alarm(0)
                continue
            except Exception as e:
                print(f"Error processing paper: {pub.get('bib', {}).get('title', 'N/A')}. Error: {e}")
                continue
                
        print(f"Successfully generated {count} new papers.")
        
    except TimeoutError:
        print("Fatal: The request to Google Scholar timed out. This usually means the IP is blocked or captcha is required.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch data from Google Scholar: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

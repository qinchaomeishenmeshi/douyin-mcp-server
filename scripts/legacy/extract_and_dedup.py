#!/usr/bin/env python3
"""从新 xlsx 提取链接，与已下载去重，输出新增链接"""
import re
import json
import openpyxl

# 1. 提取新 xlsx 中的所有链接
wb = openpyxl.load_workbook('/Users/cherishxn/Downloads/美食爆款钩子-all.xlsx')
ws = wb.active

all_links = []
for row in ws.iter_rows(min_row=2, values_only=True):
    for cell in row:
        if not cell or not isinstance(cell, str):
            continue
        # 提取短链接
        matches = re.findall(r'(https?://v\.douyin\.com/[A-Za-z0-9_-]+/?)', cell)
        for link in matches:
            link = link.rstrip('/')
            all_links.append(link)

print(f"新 xlsx 中提取到 {len(all_links)} 条链接")

# 2. 加载已下载视频的链接信息
existing_links = set()
existing_results = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/美食爆款钩子_转文字结果.json"
if True:
    # 也从 video_links.json 加载
    links_file = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/video_links.json"
    if True:
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                old_links = json.load(f)
                for item in old_links:
                    link = item.get('link', '').rstrip('/')
                    if link:
                        existing_links.add(link)
            print(f"已下载链接数: {len(existing_links)}")
        except:
            print("无法加载已下载链接")

# 3. 去重
new_links = []
seen = set()
for link in all_links:
    if link in existing_links:
        continue
    if link in seen:
        continue
    seen.add(link)
    new_links.append(link)

print(f"去重后新增链接: {len(new_links)} 条")

# 4. 保存新增链接
output = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/video_links_new.json"
with open(output, 'w', encoding='utf-8') as f:
    json.dump([{"index": i+1, "link": link} for i, link in enumerate(new_links)], f, ensure_ascii=False, indent=2)
print(f"新增链接已保存: {output}")

# 5. 打印前10条预览
for i, link in enumerate(new_links[:10], 1):
    print(f"  [{i}] {link}")
if len(new_links) > 10:
    print(f"  ... 还有 {len(new_links)-10} 条")

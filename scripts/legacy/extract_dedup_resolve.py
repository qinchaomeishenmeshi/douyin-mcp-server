#!/usr/bin/env python3
"""
从新 xlsx 提取链接 → 解析短链接获取 aweme_id → 与已下载去重 → 输出新增链接
"""
import re
import json
import os
import glob
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apiproxy.douyin.douyin import Douyin

# ========== 1. 提取新 xlsx 中的所有链接 ==========
import openpyxl
wb = openpyxl.load_workbook('/Users/cherishxn/Downloads/美食爆款钩子-all.xlsx')
ws = wb.active

all_links = []
seen_links = set()
for row in ws.iter_rows(min_row=2, values_only=True):
    for cell in row:
        if not cell or not isinstance(cell, str):
            continue
        matches = re.findall(r'(https?://v\.douyin\.com/[A-Za-z0-9_-]+/?)', cell)
        for link in matches:
            link = link.rstrip('/')
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)

print(f"新 xlsx 中提取到 {len(all_links)} 条唯一链接")

# ========== 2. 获取已下载视频的 aweme_id 集合 ==========
base = str(ROOT / 'downloads/美食爆款钩子')
existing_ids = set()
for d in sorted(os.listdir(base)):
    full = os.path.join(base, d)
    if not os.path.isdir(full):
        continue
    result_files = glob.glob(os.path.join(full, '**', '*_result.json'), recursive=True)
    for rf in result_files:
        try:
            with open(rf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            aid = data.get('aweme_id', '')
            if aid:
                existing_ids.add(str(aid))
        except:
            pass

print(f"已下载视频 aweme_id 数: {len(existing_ids)}")

# ========== 3. 解析短链接获取 key_type + key ==========
dy = Douyin()
resolved = []  # [{link, key_type, key}]

for i, link in enumerate(all_links, 1):
    print(f"[{i}/{len(all_links)}] 解析: {link}", end="")
    try:
        key_type, key = dy.getKey(link)
        if key_type and key:
            resolved.append({"link": link, "key_type": key_type, "key": str(key)})
            print(f" → {key_type}: {key}")
        else:
            print(f" ❌ 无结果")
    except Exception as e:
        print(f" ❌ {e}")
    time.sleep(0.3)

print(f"\n成功解析: {len(resolved)}/{len(all_links)}")

# ========== 4. 去重：只保留 aweme 类型且未下载的 ==========
new_items = []
duplicated = 0
skipped_type = 0

for item in resolved:
    if item["key_type"] != "aweme":
        skipped_type += 1
        continue
    if item["key"] in existing_ids:
        duplicated += 1
        continue
    new_items.append({
        "index": len(new_items) + 1,
        "link": item["link"],
        "aweme_id": item["key"]
    })

print(f"重复(已下载): {duplicated}, 非aweme类型: {skipped_type}, 新增需下载: {len(new_items)}")

# ========== 5. 保存 ==========
output = str(ROOT / "video_links_new.json")
with open(output, 'w', encoding='utf-8') as f:
    json.dump(new_items, f, ensure_ascii=False, indent=2)
print(f"新增链接已保存: {output}")

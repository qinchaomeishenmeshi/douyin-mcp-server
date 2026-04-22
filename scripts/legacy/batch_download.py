#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量下载表格中的抖音视频
"""
import sys
import os
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apiproxy.douyin.douyin import Douyin
from apiproxy.douyin.download import Download
from apiproxy.douyin import douyin_headers
from apiproxy.common import utils

SAVE_DIR = str(ROOT / "downloads/美食爆款钩子")
Path(SAVE_DIR).mkdir(parents=True, exist_ok=True)

# 读取链接
links = []
with open(ROOT / "links.txt", "r") as f:
    for line in f:
        line = line.strip()
        if line:
            parts = line.split("\t")
            if len(parts) >= 2:
                links.append({"row": parts[0], "url": parts[1]})

print(f"共 {len(links)} 个视频待下载")
print(f"保存目录: {SAVE_DIR}")
print("=" * 60)

dy = Douyin(database=False)
dl = Download(
    headers=douyin_headers,
    folder_style=True,
    music=True,
    cover=True,
    avatar=False,
    json_data=True,
    progress_bar=False,
    thread=3,
)

results = []
success_count = 0
fail_count = 0

for i, item in enumerate(links, 1):
    url = item["url"]
    row = item["row"]
    print(f"\n[{i}/{len(links)}] 处理: {url}")
    
    try:
        # 解析链接
        share_url = dy.getShareLink(url)
        key_type, key = dy.getKey(share_url)
        
        if key_type != "aweme":
            print(f"  ⚠️ 非作品链接: {key_type}")
            fail_count += 1
            continue
        
        # 获取作品详情（会自动走 Playwright fallback）
        aweme_data = dy.getAwemeInfo(key)
        if not aweme_data:
            print(f"  ❌ 获取作品详情失败")
            fail_count += 1
            continue
        
        # 下载
        desc = aweme_data.get("desc", "")[:30]
        print(f"  📥 下载: {desc}...")
        
        save_path = Path(SAVE_DIR) / f"video_{i:03d}"
        save_path.mkdir(parents=True, exist_ok=True)
        
        dl.download(awemeList=[aweme_data], savePath=save_path)
        
        # 记录结果
        result = {
            "index": i,
            "row": row,
            "aweme_id": key,
            "desc": aweme_data.get("desc", ""),
            "author": aweme_data.get("author", ""),
            "save_path": str(save_path),
            "status": "success"
        }
        results.append(result)
        success_count += 1
        print(f"  ✅ 完成")
        
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        fail_count += 1
        results.append({
            "index": i,
            "row": row,
            "url": url,
            "status": "failed",
            "error": str(e)
        })
    
    # 每 10 个暂停一下，避免频率限制
    if i % 10 == 0:
        print(f"\n  ⏸️ 已处理 {i} 个，暂停 3 秒...")
        time.sleep(3)

# 保存结果
result_file = Path(SAVE_DIR) / "download_results.json"
with open(result_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print(f"下载完成!")
print(f"  成功: {success_count}")
print(f"  失败: {fail_count}")
print(f"  结果记录: {result_file}")
print("=" * 60)

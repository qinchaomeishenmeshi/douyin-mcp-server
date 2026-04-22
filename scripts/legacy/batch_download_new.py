#!/usr/bin/env python3
"""批量下载新增的 136 个视频"""
import json
import os
import sys
import time
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apiproxy.douyin.douyin import Douyin
from apiproxy.douyin.download import Download

SAVE_BASE = str(ROOT / "downloads/美食爆款钩子")
LINKS_FILE = str(ROOT / "video_links_new.json")
PROGRESS_FILE = str(ROOT / "batch_new_progress.json")
LOG_FILE = str(ROOT / "batch_download_new.log")

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# 加载链接
with open(LINKS_FILE, 'r', encoding='utf-8') as f:
    links = json.load(f)

# 加载进度
progress = {"done": 0, "success": 0, "fail": 0, "completed_ids": []}
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
        progress = json.load(f)

# 找到已有视频目录的最大编号
existing_dirs = [d for d in os.listdir(SAVE_BASE) if d.startswith('video_')]
max_idx = max([int(d.replace('video_', '')) for d in existing_dirs]) if existing_dirs else 0

from apiproxy.douyin import douyin_headers

dy = Douyin()
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

log(f"开始批量下载，新增 {len(links)} 个，已完成 {progress['done']}, 起始编号 {max_idx}")

for item in links:
    idx = item['index']
    link = item['link']
    aweme_id = item['aweme_id']
    
    # 跳过已完成
    if aweme_id in progress['completed_ids']:
        continue
    
    max_idx += 1
    save_dir = os.path.join(SAVE_BASE, f"video_{max_idx:03d}")
    
    log(f"[{idx}/{len(links)}] 下载 {link} → video_{max_idx:03d}")
    
    try:
        # 获取视频信息
        aweme_data = dy.getAwemeInfo(aweme_id)
        if not aweme_data or not aweme_data.get('aweme_id'):
            log(f"  ❌ 获取详情失败")
            progress['fail'] += 1
            progress['done'] += 1
            progress['completed_ids'].append(aweme_id)
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False)
            continue
        
        # 下载
        dl.download(awemeList=[aweme_data], savePath=save_dir)
        log(f"  ✅ 下载成功")
        progress['success'] += 1
        
    except Exception as e:
        log(f"  ❌ 下载异常: {e}")
        progress['fail'] += 1
    
    progress['done'] += 1
    progress['completed_ids'].append(aweme_id)
    
    # 保存进度
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False)

log(f"\n下载完成! 成功: {progress['success']}, 失败: {progress['fail']}, 总计: {progress['done']}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查批量下载进度"""
import json
from pathlib import Path

save_dir = Path("/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/downloads/美食爆款钩子")
result_file = save_dir / "download_results.json"

if result_file.exists():
    with open(result_file, "r", encoding="utf-8") as f:
        results = json.load(f)
    success = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "failed")
    total = len(results)
    print(f"下载进度: {total}/100")
    print(f"  成功: {success}")
    print(f"  失败: {failed}")
else:
    # 直接数目录
    if save_dir.exists():
        dirs = [d for d in save_dir.iterdir() if d.is_dir() and d.name.startswith("video_")]
        print(f"已下载: {len(dirs)}/100")
    else:
        print("尚未开始下载")

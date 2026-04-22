#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载完成后自动运行 ASR 转文字
用法: python3 auto_asr_after_download.py
"""
import sys
import os
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAVE_DIR = ROOT / "downloads/美食爆款钩子"
RESULT_FILE = SAVE_DIR / "download_results.json"

# 等待下载完成
print("等待下载完成...")
while True:
    if RESULT_FILE.exists():
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
        if len(results) >= 100:
            print(f"下载完成! 共 {len(results)} 个")
            break
    #  also check if download process is gone
    import subprocess
    try:
        subprocess.run(["pgrep", "-f", "batch_download.py"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # process gone, check results
        if RESULT_FILE.exists():
            with open(RESULT_FILE, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"下载进程已结束，共 {len(results)} 个结果")
            break
    print(f"  当前进度: {len(results) if RESULT_FILE.exists() else 0}/100，继续等待...")
    time.sleep(30)

# 加载 ASR
print("\n加载 ASR 模型...")
from apiproxy.common.asr import get_asr_processor

processor = get_asr_processor()
print("ASR 模型加载完成")

# 处理每个成功的视频
success_results = [r for r in results if r.get("status") == "success"]
print(f"\n开始 ASR 转文字，共 {len(success_results)} 个视频")

asr_results = []
for i, item in enumerate(success_results, 1):
    video_dir = Path(item["save_path"])
    # 找到视频文件
    video_files = list(video_dir.rglob("*_video.mp4"))
    if not video_files:
        print(f"  [{i}/{len(success_results)}] 未找到视频文件: {video_dir}")
        asr_results.append({"index": i, "aweme_id": item["aweme_id"], "status": "no_video_file"})
        continue
    
    video_path = video_files[0]
    print(f"  [{i}/{len(success_results)}] ASR: {video_path.name[:40]}...")
    
    try:
        result = processor.process_media_file(
            str(video_path),
            str(video_dir),
            save_formats=["txt"]
        )
        if result.get("status") == "success":
            txt_files = result.get("saved_files", [])
            text = result.get("text", "")
            print(f"    ✅ 完成，文字长度: {len(text)}")
            asr_results.append({
                "index": i,
                "aweme_id": item["aweme_id"],
                "desc": item.get("desc", ""),
                "status": "success",
                "text": text,
                "text_file": txt_files[0] if txt_files else ""
            })
        else:
            print(f"    ❌ ASR 失败: {result.get('reason', 'Unknown')}")
            asr_results.append({"index": i, "aweme_id": item["aweme_id"], "status": "failed", "reason": result.get("reason", "")})
    except Exception as e:
        print(f"    ❌ 异常: {e}")
        asr_results.append({"index": i, "aweme_id": item["aweme_id"], "status": "error", "reason": str(e)})

# 保存 ASR 结果
asr_result_file = SAVE_DIR / "asr_results.json"
with open(asr_result_file, "w", encoding="utf-8") as f:
    json.dump(asr_results, f, ensure_ascii=False, indent=2)

# 生成汇总文本
summary_file = SAVE_DIR / "all_texts.txt"
with open(summary_file, "w", encoding="utf-8") as f:
    for r in asr_results:
        if r.get("status") == "success":
            f.write(f"【{r.get('desc', '无标题')[:30]}】\n")
            f.write(f"aweme_id: {r['aweme_id']}\n")
            f.write(f"{text}\n")
            f.write("-" * 60 + "\n\n")

print(f"\n{'='*60}")
print(f"ASR 完成!")
print(f"  成功: {sum(1 for r in asr_results if r.get('status')=='success')}")
print(f"  失败: {sum(1 for r in asr_results if r.get('status')!='success')}")
print(f"  ASR 结果: {asr_result_file}")
print(f"  汇总文本: {summary_file}")
print(f"{'='*60}")

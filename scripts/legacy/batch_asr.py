#!/usr/bin/env python3
"""批量 ASR：将已下载视频的语音转为文字"""
import os
import glob
import json
import time
import sys

BASE_DIR = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/downloads/美食爆款钩子"
OUTPUT_FILE = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/美食爆款钩子_转文字结果.json"
OUTPUT_CSV = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/美食爆款钩子_转文字结果.csv"

# 加载原始表格的链接-标题映射
LINKS_FILE = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/video_links.json"

print("=" * 60)
print("批量 ASR 语音转文字")
print("=" * 60)

# 加载 faster-whisper
from faster_whisper import WhisperModel
print("加载 faster-whisper small 模型...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("✅ 模型加载完成")

# 加载链接映射
links_map = {}
if os.path.exists(LINKS_FILE):
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        links_data = json.load(f)
        for item in links_data:
            links_map[item["index"]] = item

# 扫描已下载的视频
results = []
video_dirs = sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])

print(f"发现 {len(video_dirs)} 个视频目录")

for idx, video_dir in enumerate(video_dirs, 1):
    full_dir = os.path.join(BASE_DIR, video_dir)
    
    # 查找 mp4 文件
    mp4_files = glob.glob(os.path.join(full_dir, "**", "*_video.mp4"), recursive=True)
    if not mp4_files:
        # 也可能是直接 mp4
        mp4_files = glob.glob(os.path.join(full_dir, "**", "*.mp4"), recursive=True)
    
    if not mp4_files:
        print(f"[{idx}/{len(video_dirs)}] ❌ {video_dir} - 未找到视频文件")
        continue
    
    video_path = mp4_files[0]
    video_name = os.path.basename(video_path).replace("_video.mp4", "")
    
    # 检查是否已有结果
    result_json = glob.glob(os.path.join(full_dir, "**", "*_result.json"), recursive=True)
    
    print(f"[{idx}/{len(video_dirs)}] 🎬 {video_name[:50]}...")
    
    try:
        start = time.time()
        segments, info = model.transcribe(video_path, language="zh", beam_size=5)
        text = "".join([s.text for s in segments])
        elapsed = time.time() - start
        
        # 获取视频信息
        video_info = {}
        if result_json:
            try:
                with open(result_json[0], "r", encoding="utf-8") as f:
                    video_info = json.load(f)
            except:
                pass
        
        result = {
            "index": idx,
            "video_dir": video_dir,
            "video_name": video_name,
            "duration": round(info.duration, 1),
            "asr_time": round(elapsed, 1),
            "text": text,
            "video_info": video_info,
        }
        
        # 合并链接信息
        link_info = links_map.get(idx, {})
        if link_info:
            result["original_title"] = link_info.get("title", "")
            result["original_link"] = link_info.get("link", "")
        
        results.append(result)
        print(f"  ✅ 时长 {info.duration:.1f}s, 识别耗时 {elapsed:.1f}s, 文字 {len(text)} 字")
        
    except Exception as e:
        print(f"  ❌ 识别失败: {e}")
        results.append({
            "index": idx,
            "video_dir": video_dir,
            "video_name": video_name,
            "error": str(e),
        })

# 保存 JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n✅ JSON 结果已保存: {OUTPUT_FILE}")

# 保存 CSV
import csv
with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["序号", "视频名称", "时长(秒)", "语音转文字", "原始链接"])
    for r in results:
        writer.writerow([
            r.get("index", ""),
            r.get("video_name", ""),
            r.get("duration", ""),
            r.get("text", ""),
            r.get("original_link", ""),
        ])
print(f"✅ CSV 结果已保存: {OUTPUT_CSV}")

# 打印摘要
success = sum(1 for r in results if "text" in r)
fail = sum(1 for r in results if "error" in r)
total_text = sum(len(r.get("text", "")) for r in results)
print(f"\n{'=' * 60}")
print(f"总计: {len(results)} 个视频, 成功 {success}, 失败 {fail}")
print(f"总文字量: {total_text} 字")

#!/usr/bin/env python3
"""批量 ASR：将新增下载视频的语音转为文字（增量，只处理新增的）"""
import os
import glob
import json
import time
import sys

BASE_DIR = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/downloads/美食爆款钩子"
OUTPUT_FILE = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/美食爆款钩子_all_转文字结果.json"

# 已有的旧结果
OLD_RESULT = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/美食爆款钩子_转文字结果.json"

# 加载链接映射
LINKS_OLD = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/video_links.json"
LINKS_NEW = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/video_links_new.json"

print("=" * 60)
print("批量 ASR 语音转文字（增量）")
print("=" * 60)

from faster_whisper import WhisperModel
print("加载 faster-whisper small 模型...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("✅ 模型加载完成")

# 加载链接映射
links_map = {}
for lf in [LINKS_OLD, LINKS_NEW]:
    if os.path.exists(lf):
        with open(lf, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                links_map[item.get("index", 0)] = item

# 加载旧结果
existing_results = {}
if os.path.exists(OLD_RESULT):
    with open(OLD_RESULT, "r", encoding="utf-8") as f:
        old_data = json.load(f)
        for r in old_data:
            existing_results[r.get("video_dir", "")] = r

# 扫描所有视频目录
results = []
video_dirs = sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d)) and d.startswith('video_')])

print(f"发现 {len(video_dirs)} 个视频目录，已有 {len(existing_results)} 条结果")

for idx, video_dir in enumerate(video_dirs, 1):
    full_dir = os.path.join(BASE_DIR, video_dir)
    
    # 跳过已有结果
    if video_dir in existing_results:
        results.append(existing_results[video_dir])
        continue
    
    # 查找 mp4 文件
    mp4_files = glob.glob(os.path.join(full_dir, "**", "*_video.mp4"), recursive=True)
    if not mp4_files:
        mp4_files = glob.glob(os.path.join(full_dir, "**", "*.mp4"), recursive=True)
    
    if not mp4_files:
        print(f"[{idx}/{len(video_dirs)}] ❌ {video_dir} - 未找到视频文件")
        continue
    
    video_path = mp4_files[0]
    video_name = os.path.basename(video_path).replace("_video.mp4", "")
    
    # 获取视频信息
    video_info = {}
    result_json = glob.glob(os.path.join(full_dir, "**", "*_result.json"), recursive=True)
    if result_json:
        try:
            with open(result_json[0], "r", encoding="utf-8") as f:
                video_info = json.load(f)
        except:
            pass
    
    print(f"[{idx}/{len(video_dirs)}] 🎬 {video_name[:50]}...")
    
    try:
        start = time.time()
        segments, info = model.transcribe(video_path, language="zh", beam_size=5)
        text = "".join([s.text for s in segments])
        elapsed = time.time() - start
        
        result = {
            "index": idx,
            "video_dir": video_dir,
            "video_name": video_name,
            "duration": round(info.duration, 1),
            "asr_time": round(elapsed, 1),
            "text": text,
            "video_info": video_info,
            "aweme_id": video_info.get("aweme_id", ""),
        }
        
        results.append(result)
        print(f"  ✅ 时长 {info.duration:.1f}s, 识别耗时 {elapsed:.1f}s, 文字 {len(text)} 字")
        
    except Exception as e:
        print(f"  ❌ 识别失败: {e}")
        results.append({
            "index": idx,
            "video_dir": video_dir,
            "video_name": video_name,
            "error": str(e),
            "aweme_id": video_info.get("aweme_id", ""),
        })

# 保存 JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n✅ JSON 结果已保存: {OUTPUT_FILE}")

# 摘要
success = sum(1 for r in results if "text" in r)
fail = sum(1 for r in results if "error" in r)
total_text = sum(len(r.get("text", "")) for r in results)
total_duration = sum(r.get("duration", 0) for r in results)
print(f"总计: {len(results)} 个视频, 成功 {success}, 失败 {fail}")
print(f"总文字量: {total_text} 字, 总时长: {total_duration:.0f}s ({total_duration/60:.1f}分钟)")

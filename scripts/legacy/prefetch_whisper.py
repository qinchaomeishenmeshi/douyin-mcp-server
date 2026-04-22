#!/usr/bin/env python3
"""预加载 faster-whisper 模型 + 测试识别"""
import os
import glob
import sys

print("正在下载/加载 faster-whisper small 模型...")
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")
print("✅ faster-whisper small 模型加载完成！")

# 找一个已下载的视频做测试
base = "/Users/cherishxn/workspace/pycharm_projects/douyin-mcp-server/downloads/美食爆款钩子"
test_video = None
for d in sorted(os.listdir(base)):
    full = os.path.join(base, d)
    if os.path.isdir(full):
        mp4s = glob.glob(os.path.join(full, "**", "*_video.mp4"), recursive=True)
        if mp4s:
            test_video = mp4s[0]
            break

if test_video:
    print(f"测试视频: {test_video}")
    segments, info = model.transcribe(test_video, language="zh")
    text = "".join([s.text for s in segments])
    print(f"✅ 测试识别成功！时长: {info.duration:.1f}s")
    print(f"识别结果: {text[:300]}")
else:
    print("暂无已下载视频可测试")

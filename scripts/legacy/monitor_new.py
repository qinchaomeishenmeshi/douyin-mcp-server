#!/usr/bin/env python3
"""监控新增视频下载进度，完成后自动启动 ASR + 生成 xlsx"""
import subprocess
import time
import os
import json
import sys
from pathlib import Path

PYTHON = "/usr/local/bin/python3.11"
ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIR = ROOT / "scripts" / "legacy"
BASE_DIR = str(ROOT)
PROGRESS_FILE = f"{BASE_DIR}/batch_new_progress.json"
LOG_FILE = f"{BASE_DIR}/monitor_new.log"

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

log("=" * 60)
log("监控新增视频下载进度")

# 等待下载进程完成
while True:
    # 检查下载进程
    result = subprocess.run(["pgrep", "-f", "batch_download_new"], capture_output=True, text=True)
    if not result.stdout.strip():
        log("下载进程已结束")
        break
    
    # 检查进度
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            prog = json.load(f)
        log(f"下载进度: {prog['done']}/136, 成功: {prog['success']}, 失败: {prog['fail']}")
    else:
        log("等待下载开始...")
    
    time.sleep(60)

# 等待文件写入完成
log("等待 5 秒确保文件写入完成...")
time.sleep(5)

# 启动 ASR
log("启动批量 ASR...")
try:
    result = subprocess.run(
        [PYTHON, str(LEGACY_DIR / "batch_asr_new.py")],
        timeout=3600
    )
    log(f"ASR 完成，退出码: {result.returncode}")
except Exception as e:
    log(f"ASR 异常: {e}")

# 生成 xlsx
log("生成 xlsx...")
try:
    result = subprocess.run(
        [PYTHON, str(LEGACY_DIR / "gen_all_xlsx.py")],
        timeout=60
    )
    log(f"XLSX 生成完成，退出码: {result.returncode}")
except Exception as e:
    log(f"XLSX 生成异常: {e}")

log("全部完成！")

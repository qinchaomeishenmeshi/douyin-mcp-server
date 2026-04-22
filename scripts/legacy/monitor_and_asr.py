#!/usr/bin/env python3
"""监控下载进度，完成后自动启动 ASR"""
import subprocess
import time
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIR = ROOT / "scripts" / "legacy"

CHECK_SCRIPT = str(LEGACY_DIR / "check_progress.py")
ASR_SCRIPT = str(LEGACY_DIR / "batch_asr.py")
PYTHON = "/usr/local/bin/python3.11"
LOG_FILE = str(ROOT / "monitor_and_asr.log")

def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

log("=" * 60)
log("监控脚本启动")

# 等待下载进程完成
while True:
    # 检查下载进程是否还在
    result = subprocess.run(["ps", "-p", "31918"], capture_output=True, text=True)
    if result.returncode != 0:
        log("下载进程已结束，检查最终进度...")
        break
    
    # 检查进度
    try:
        prog = subprocess.run(
            ["/Library/Frameworks/Python.framework/Versions/3.11/bin/python3", CHECK_SCRIPT],
            capture_output=True, text=True, timeout=10
        )
        log(prog.stdout.strip())
    except:
        log("进度检查超时")
    
    time.sleep(60)  # 每分钟检查一次

# 下载完成，等待 5 秒确保文件写入完成
log("等待 5 秒确保文件写入完成...")
time.sleep(5)

# 启动 ASR
log("启动批量 ASR...")
try:
    result = subprocess.run(
        [PYTHON, ASR_SCRIPT],
        capture_output=False,  # 直接输出到终端
        timeout=3600,  # 1 小时超时
    )
    log(f"ASR 完成，退出码: {result.returncode}")
except subprocess.TimeoutExpired:
    log("ASR 超时（1小时）")
except Exception as e:
    log(f"ASR 异常: {e}")

#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import json
import time
import requests
import threading
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from pathlib import Path
# import asyncio  # 暂时注释掉
# import aiohttp  # 暂时注释掉
import logging
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from apiproxy.douyin import douyin_headers
from apiproxy.common import utils

logger = logging.getLogger("douyin_downloader")
console = Console()

class Download(object):
    def __init__(self, headers, folder_style, music=True, video=True, cover=True, avatar=True, json_data=True, progress_bar=True, callback=None, thread=5):
        self.headers = headers
        self.folder_style = folder_style
        self.video = video
        self.music = music
        self.cover = cover
        self.avatar = avatar
        self.json_data = json_data
        self.progress_bar = progress_bar
        self.callback = callback
        self.thread = thread
        self.console = Console()
        self.retry_times = 3
        self.chunk_size = 8192
        self.timeout = 30
        self.total_progress = 0
        self.lock = threading.Lock()

    def _download_media(self, url: str, path: Path, desc: str, progress: Progress) -> bool:
        """通用下载方法，将Progress对象传递给断点续传下载器"""
        if path.exists():
            # self.console.print(f"[cyan]⏭️  跳过已存在: {desc}[/]")
            return True
        return self.download_with_resume(url, path, desc, progress)

    def _get_first_url(self, url_list: list) -> str:
        """安全地获取URL列表中的第一个URL"""
        if isinstance(url_list, list) and len(url_list) > 0:
            return url_list[0]
        return None

    def _download_media_files(self, aweme: dict, path: Path, name: str, desc: str, progress: Progress) -> None:
        """下载所有媒体文件，传递Progress对象"""
        try:
            # 下载视频
            if self.video and aweme["awemeType"] == 0:
                video_path = path / f"{name}_video.mp4"
                url_list = aweme.get("video", {}).get("play_addr", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    if not self._download_media(url, video_path, f"[视频]{desc}", progress):
                        raise Exception("视频下载失败")
                else:
                    logger.warning(f"视频URL为空: {desc}")

            # 下载图集
            elif aweme["awemeType"] == 1:
                for i, image in enumerate(aweme.get("images", [])):
                    url_list = image.get("url_list", [])
                    if url := self._get_first_url(url_list):
                        image_path = path / f"{name}_image_{i}.jpeg"
                        if not self._download_media(url, image_path, f"[图集{i+1}]{desc}", progress):
                            raise Exception(f"图片{i+1}下载失败")
                    else:
                        logger.warning(f"图片{i+1} URL为空: {desc}")
            
            # 下载音频
            if self.music:
                url_list = aweme.get("music", {}).get("play_url", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    music_name = utils.replaceStr(aweme["music"]["title"])
                    music_path = path / f"{name}_music_{music_name}.mp3"
                    if not self._download_media(url, music_path, f"[音乐]{desc}", progress):
                        logger.warning(f"音乐下载失败: {desc}")
            
            # 下载封面
            if self.cover and aweme["awemeType"] == 0:
                url_list = aweme.get("video", {}).get("cover", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    cover_path = path / f"{name}_cover.jpeg"
                    if not self._download_media(url, cover_path, f"[封面]{desc}", progress):
                        logger.warning(f"封面下载失败: {desc}")

            # 下载头像
            if self.avatar:
                url_list = aweme.get("author", {}).get("avatar", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    avatar_path = path / f"{name}_avatar.jpeg"
                    if not self._download_media(url, avatar_path, f"[头像]{desc}", progress):
                        logger.warning(f"头像下载失败: {desc}")
        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")

    def awemeDownload(self, awemeDict: dict, savePath: Path, progress: Progress) -> None:
        """下载单个作品的所有内容，接收Progress对象"""
        if not awemeDict:
            logger.warning("无效的作品数据")
            return
        try:
            save_path = Path(savePath)
            save_path.mkdir(parents=True, exist_ok=True)
            file_name = f"{awemeDict['create_time']}_{utils.replaceStr(awemeDict['desc'])}"
            aweme_path = save_path / file_name if self.folder_style else save_path
            aweme_path.mkdir(exist_ok=True)
            
            if self.json_data:
                self._save_json(aweme_path / f"{file_name}_result.json", awemeDict)
            
            desc = file_name[:30]
            self._download_media_files(awemeDict, aweme_path, file_name, desc, progress)
        except Exception as e:
            logger.error(f"处理作品时出错: {awemeDict.get('desc', '未知作品')} - {str(e)}")
            raise  # 重新抛出异常，以便线程池可以捕获

    def _save_json(self, path: Path, data: dict) -> None:
        """保存JSON数据"""
        try:
            with open(path, "w", encoding='utf-8') as f:
                json.dump(data, ensure_ascii=False, indent=2, fp=f)
        except Exception as e:
            logger.error(f"保存JSON失败: {path}, 错误: {str(e)}")

    def download(self, awemeList: List[dict], savePath: Path):
        if not awemeList:
            self.console.print("[yellow]⚠️  没有找到可下载的内容[/]")
            return

        save_path = Path(savePath)
        save_path.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        total_count = len(awemeList)
        success_count = 0
        
        if self.progress_bar:
            self.console.print(Panel(
                Text.assemble(
                    ("下载配置\n", "bold cyan"),
                    (f"总数: {total_count} 个作品\n", "cyan"),
                    (f"线程: {self.thread}\n", "cyan"),
                    (f"保存路径: {save_path}\n", "cyan"),
                    (f"下载项: {'视频 ' if self.video else ''}{'音频 ' if self.music else ''}{'封面 ' if self.cover else ''}{'头像 ' if self.avatar else ''}{'JSON ' if self.json_data else ''}", "cyan")
                ),
                title="抖音下载器",
                border_style="cyan"
            ))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=False  # 设置为False，以便在下载完成时仍可见
        ) as progress:
            main_task = progress.add_task("[cyan]📥 批量下载进度", total=total_count)
            
            with ThreadPoolExecutor(max_workers=self.thread) as executor:
                future_to_aweme = {executor.submit(self.awemeDownload, aweme, save_path, progress): aweme for aweme in awemeList}
                
                downloaded_count = 0
                for future in as_completed(future_to_aweme):
                    downloaded_count += 1
                    aweme = future_to_aweme[future]
                    aweme_desc = aweme.get('desc', '未知作品')[:30]
                    try:
                        future.result()
                        success_count += 1
                        # progress.print(f"[green]✅ 下载成功: {aweme_desc}[/]")
                    except Exception as exc:
                        progress.print(f"[red]❌ 下载失败: {aweme_desc} - {exc}[/]")
                    
                    # 调用回调函数更新外部进度
                    if self.callback:
                        self.callback(downloaded_count, total_count)
                        
                    progress.update(main_task, advance=1)

        end_time = time.time()
        duration = end_time - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        self.console.print(Panel(
            Text.assemble(
                ("下载完成\n", "bold green"),
                (f"成功: {success_count}/{total_count}\n", "green"),
                (f"用时: {minutes}分{seconds}秒\n", "green"),
                (f"保存位置: {save_path}\n", "green"),
            ),
            title="下载统计",
            border_style="green"
        ))

        return success_count

    def download_with_resume(self, url: str, filepath: Path, desc: str, progress: Progress) -> bool:
        """支持断点续传的下载方法，使用传入的Progress对象"""
        task = progress.add_task(f"[cyan]└─ {desc}", total=1, start=False, visible=True)

        for attempt in range(self.retry_times):
            try:
                file_size = filepath.stat().st_size if filepath.exists() else 0
                headers = {'Range': f'bytes={file_size}-'}

                response = requests.get(url, headers={**self.headers, **headers}, stream=True, timeout=self.timeout)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0)) + file_size
                progress.update(task, total=total_size, completed=file_size)
                progress.start_task(task)

                with open(filepath, 'ab') as f:
                            for chunk in response.iter_content(chunk_size=self.chunk_size):
                                if chunk:
                                    f.write(chunk)
                            progress.update(task, advance=len(chunk))
                
                progress.update(task, description=f"[green]✔ {desc}", visible=False)
                return True

            except (requests.exceptions.RequestException, IOError) as e:
                if attempt < self.retry_times - 1:
                    wait_time = 2 ** (attempt + 1)
                    progress.update(task, description=f"[yellow]⚠️ {desc} ({e.__class__.__name__}, 等待 {wait_time}s...)", visible=True)
                    time.sleep(wait_time)
                else:
                    progress.update(task, description=f"[red]❌ {desc} ({e.__class__.__name__})", visible=True)
                    logger.error(f"下载失败，已达最大重试次数: {desc} - {e}")
                    raise e
        return False


class DownloadManager:
    """
    一个简单的下载管理器，用于控制并发下载任务
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_workers=3):
        # 初始化只执行一次
        if not hasattr(self, 'executor'):
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            self.futures = {}
            self.console = Console()

    def submit_task(self, func, *args, **kwargs):
        """提交下载任务"""
        future = self.executor.submit(func, *args, **kwargs)
        task_id = f"task_{int(time.time() * 1000)}"
        self.futures[task_id] = future
        self.console.print(f"✅ [bold green]任务 {task_id} 已提交[/]")
        return task_id

    def get_task_status(self, task_id: str):
        """获取任务状态"""
        future = self.futures.get(task_id)
        if not future:
            return {"status": "not_found", "message": "任务不存在"}

        if future.running():
            return {"status": "running", "message": "任务正在运行"}
        elif future.done():
            try:
                result = future.result()
                return {"status": "completed", "message": "任务已完成", "result": result}
            except Exception as e:
                return {"status": "failed", "message": "任务失败", "error": str(e)}
        else:
            return {"status": "pending", "message": "任务等待中"}
    
    def download_with_resume(self, url, filepath, callback=None):
        # 检查是否存在部分下载的文件
        resume_header = {}
        if filepath.exists():
            file_size = filepath.stat().st_size
            resume_header['Range'] = f'bytes={file_size}-'
        else:
            file_size = 0

        try:
            with requests.get(url, headers={**douyin_headers, **resume_header}, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0)) + file_size
                with open(filepath, 'ab') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            if callback:
                                callback(len(chunk))
            return True
        except Exception as e:
            self.console.print(f"❌ [bold red]下载失败: {filepath.name} - {str(e)}[/]")
            return False


if __name__ == "__main__":
    pass

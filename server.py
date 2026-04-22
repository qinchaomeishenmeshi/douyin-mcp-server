#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音下载器 MCP Server
将 douyin-downloader 的核心能力封装为 MCP 工具服务

工具列表:
  - parse_link:      解析抖音分享链接，获取资源类型和ID
  - get_video_info:  获取单个作品(视频/图集)详情
  - get_user_info:   获取用户主页作品列表
  - get_user_detail: 获取用户详细信息(昵称/粉丝/签名等)
  - get_mix_info:    获取合集作品列表
  - get_music_info:  获取音乐(原声)下的作品列表
  - get_live_info:   获取直播间信息
  - download:        下载作品(视频/图集/音乐/封面)
  - download_user:   批量下载用户主页作品
  - get_task_status: 查询异步下载任务状态
"""

import argparse
import time
import threading
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("douyin-mcp")

# ---------------------------------------------------------------------------
# 复用 vendored douyin runtime 模块
# ---------------------------------------------------------------------------
from apiproxy.douyin.douyin import Douyin
from apiproxy.douyin.download import Download
from apiproxy.douyin import douyin_headers
from apiproxy.common import utils

# ---------------------------------------------------------------------------
# MCP 实例
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="douyin-downloader",
    instructions="抖音下载器 MCP Server - 解析链接 / 获取信息 / 批量下载。支持视频/图集/用户主页/合集/音乐/直播等内容的解析和下载。",
)
VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# 全局状态: 异步任务管理
# ---------------------------------------------------------------------------
_tasks: dict = {}
_task_lock = threading.Lock()


def _generate_task_id() -> str:
    return f"task_{int(time.time() * 1000)}"


# ===================================================================
# Tool 1: parse_link - 解析分享链接
# ===================================================================
@mcp.tool()
def parse_link(url: str) -> dict:
    """解析抖音分享链接，获取资源类型和资源ID

    Args:
        url: 抖音分享链接，如 https://v.douyin.com/xxx/ 或 https://www.douyin.com/xxx

    Returns:
        {"key_type": "user|aweme|mix|music|live", "key": "资源ID"}
    """
    try:
        dy = Douyin(database=False)
        share_url = dy.getShareLink(url)
        key_type, key = dy.getKey(share_url)
        if key_type is None:
            return {"error": "无法解析该链接，请确认链接格式正确"}
        return {"key_type": key_type, "key": key}
    except Exception as e:
        return {"error": f"解析链接失败: {str(e)}"}


# ===================================================================
# Tool 2: get_video_info - 获取单个作品详情
# ===================================================================
@mcp.tool()
def get_video_info(aweme_id: str) -> dict:
    """获取单个抖音作品(视频/图集)的详细信息

    Args:
        aweme_id: 作品ID，可通过 parse_link 获取

    Returns:
        作品详情: 描述、作者、视频/图集URL、统计数据等
    """
    try:
        dy = Douyin(database=False)
        result = dy.getAwemeInfo(aweme_id)
        if not result:
            return {"error": f"无法获取作品 {aweme_id} 的信息，可能需要更新Cookie"}
        # 精简返回，去掉空字段
        _clean_result = {}
        for k, v in result.items():
            if v != "" and v != [] and v != {}:
                _clean_result[k] = v
        return _clean_result
    except Exception as e:
        return {"error": f"获取作品信息失败: {str(e)}"}


# ===================================================================
# Tool 3: get_user_info - 获取用户作品列表
# ===================================================================
@mcp.tool()
def get_user_info(
    sec_uid: str,
    mode: str = "post",
    count: int = 35,
    number: int = 0,
    increase: bool = False,
    start_time: str = "",
    end_time: str = "",
) -> dict:
    """获取抖音用户的作品列表

    Args:
        sec_uid: 用户sec_uid，可通过 parse_link 获取
        mode: 模式选择 - post(发布作品) / like(喜欢作品)，默认post
        count: 每页数量，默认35
        number: 限制获取数量，0=不限制
        increase: 是否增量更新，默认False
        start_time: 开始时间 YYYY-MM-DD，空=不限制
        end_time: 结束时间 YYYY-MM-DD，空=不限制

    Returns:
        作品列表摘要信息
    """
    try:
        dy = Douyin(database=increase)
        aweme_list = dy.getUserInfo(
            sec_uid=sec_uid,
            mode=mode,
            count=count,
            number=number,
            increase=increase,
            start_time=start_time,
            end_time=end_time,
        )
        if not aweme_list:
            return {"error": "未获取到作品数据，可能需要更新Cookie或检查用户ID"}

        # 返回摘要，避免数据量过大
        summary = []
        for item in aweme_list:
            summary.append({
                "aweme_id": item.get("aweme_id", ""),
                "desc": item.get("desc", "")[:80],
                "awemeType": item.get("awemeType", ""),
                "create_time": item.get("create_time", ""),
                "author_nickname": item.get("author", {}).get("nickname", ""),
                "statistics": item.get("statistics", {}),
            })
        return {"total": len(summary), "items": summary}
    except Exception as e:
        return {"error": f"获取用户作品失败: {str(e)}"}


# ===================================================================
# Tool 4: get_user_detail - 获取用户详细信息
# ===================================================================
@mcp.tool()
def get_user_detail(sec_uid: str) -> dict:
    """获取抖音用户详细信息（昵称、粉丝数、签名等）

    Args:
        sec_uid: 用户sec_uid

    Returns:
        用户详情字典
    """
    try:
        dy = Douyin(database=False)
        data = dy.getUserDetailInfo(sec_uid)
        if not data or not data.get("user"):
            return {"error": "无法获取用户信息，请检查sec_uid或更新Cookie"}
        user = data["user"]
        return {
            "nickname": user.get("nickname", ""),
            "signature": user.get("signature", ""),
            "follower_count": user.get("follower_count", 0),
            "following_count": user.get("following_count", 0),
            "favoriting_count": user.get("favoriting_count", 0),
            "total_favorited": user.get("total_favorited", 0),
            "aweme_count": user.get("aweme_count", 0),
            "unique_id": user.get("unique_id", ""),
            "short_id": user.get("short_id", ""),
            "sec_uid": user.get("sec_uid", ""),
            "avatar_url": user.get("avatar_thumb", {}).get("url_list", [""])[0] if user.get("avatar_thumb") else "",
        }
    except Exception as e:
        return {"error": f"获取用户详情失败: {str(e)}"}


# ===================================================================
# Tool 5: get_mix_info - 获取合集作品列表
# ===================================================================
@mcp.tool()
def get_mix_info(
    mix_id: str,
    count: int = 35,
    number: int = 0,
    increase: bool = False,
    sec_uid: str = "",
    start_time: str = "",
    end_time: str = "",
) -> dict:
    """获取抖音合集下的作品列表

    Args:
        mix_id: 合集ID，可通过 parse_link 获取
        count: 每页数量，默认35
        number: 限制获取数量，0=不限制
        increase: 是否增量更新
        sec_uid: 用户sec_uid(增量更新时需要)
        start_time: 开始时间 YYYY-MM-DD
        end_time: 结束时间 YYYY-MM-DD

    Returns:
        合集作品列表摘要
    """
    try:
        dy = Douyin(database=increase)
        aweme_list = dy.getMixInfo(
            mix_id=mix_id,
            count=count,
            number=number,
            increase=increase,
            sec_uid=sec_uid,
            start_time=start_time,
            end_time=end_time,
        )
        if not aweme_list:
            return {"error": "未获取到合集数据"}

        summary = []
        for item in aweme_list:
            mix_info = item.get("mix_info", {})
            summary.append({
                "aweme_id": item.get("aweme_id", ""),
                "desc": item.get("desc", "")[:80],
                "awemeType": item.get("awemeType", ""),
                "create_time": item.get("create_time", ""),
                "mix_name": mix_info.get("mix_name", ""),
            })
        return {"total": len(summary), "items": summary}
    except Exception as e:
        return {"error": f"获取合集信息失败: {str(e)}"}


# ===================================================================
# Tool 6: get_music_info - 获取音乐下的作品列表
# ===================================================================
@mcp.tool()
def get_music_info(
    music_id: str,
    count: int = 35,
    number: int = 0,
    increase: bool = False,
) -> dict:
    """获取抖音音乐(原声)下的作品列表

    Args:
        music_id: 音乐ID，可通过 parse_link 获取
        count: 每页数量，默认35
        number: 限制获取数量，0=不限制
        increase: 是否增量更新

    Returns:
        音乐作品列表摘要
    """
    try:
        dy = Douyin(database=increase)
        aweme_list = dy.getMusicInfo(
            music_id=music_id,
            count=count,
            number=number,
            increase=increase,
        )
        if not aweme_list:
            return {"error": "未获取到音乐下的作品数据"}

        summary = []
        for item in aweme_list:
            music = item.get("music", {})
            summary.append({
                "aweme_id": item.get("aweme_id", ""),
                "desc": item.get("desc", "")[:80],
                "create_time": item.get("create_time", ""),
                "music_title": music.get("title", ""),
            })
        return {"total": len(summary), "items": summary}
    except Exception as e:
        return {"error": f"获取音乐信息失败: {str(e)}"}


# ===================================================================
# Tool 7: get_live_info - 获取直播间信息
# ===================================================================
@mcp.tool()
def get_live_info(web_rid: str) -> dict:
    """获取抖音直播间信息（标题、推流地址、观看人数等）

    Args:
        web_rid: 直播间web_rid，可通过 parse_link 获取

    Returns:
        直播间信息字典
    """
    try:
        dy = Douyin(database=False)
        result = dy.getLiveInfo(web_rid)
        if not result:
            return {"error": "无法获取直播间信息"}
        return {
            "status": result.get("status", ""),
            "title": result.get("title", ""),
            "nickname": result.get("nickname", ""),
            "user_count": result.get("user_count", ""),
            "display_long": result.get("display_long", ""),
            "flv_pull_url": result.get("flv_pull_url", {}),
            "partition": result.get("partition", ""),
            "sub_partition": result.get("sub_partition", ""),
            "cover": result.get("cover", ""),
            "avatar": result.get("avatar", ""),
        }
    except Exception as e:
        return {"error": f"获取直播间信息失败: {str(e)}"}


# ===================================================================
# Tool 8: download - 下载单个作品
# ===================================================================
@mcp.tool()
def download(
    url: str,
    save_path: str = "./downloads",
    music: bool = True,
    cover: bool = True,
    avatar: bool = True,
    json_data: bool = True,
    folderstyle: bool = True,
    thread: int = 3,
    cookie: str = "",
) -> dict:
    """下载抖音单个作品（视频/图集），支持自动解析链接

    Args:
        url: 抖音分享链接或网页URL
        save_path: 保存路径，默认 ./downloads
        music: 是否下载音乐，默认True
        cover: 是否下载封面，默认True
        avatar: 是否下载头像，默认True
        json_data: 是否保存JSON数据，默认True
        folderstyle: 是否使用文件夹结构，默认True
        thread: 下载线程数，默认3
        cookie: 自定义Cookie字符串，空则使用默认

    Returns:
        下载结果: 成功/失败信息
    """
    try:
        # 设置Cookie
        if cookie:
            douyin_headers["Cookie"] = cookie

        dy = Douyin(database=False)
        dl = Download(
            headers=douyin_headers,
            folder_style=folderstyle,
            music=music,
            cover=cover,
            avatar=avatar,
            json_data=json_data,
            progress_bar=False,  # MCP 模式下关闭进度条
            thread=thread,
        )

        # 解析链接
        share_url = dy.getShareLink(url)
        key_type, key = dy.getKey(share_url)

        if key_type != "aweme":
            return {"error": f"该链接不是单个作品(type={key_type})，请使用对应的批量下载工具"}

        # 获取作品信息
        aweme_data = dy.getAwemeInfo(key)
        if not aweme_data:
            return {"error": "无法获取作品信息"}

        # 创建保存目录
        save_dir = Path(save_path) / "aweme"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 执行下载
        dl.userDownload(awemeList=[aweme_data], savePath=str(save_dir))

        return {
            "success": True,
            "message": f"作品下载完成: {aweme_data.get('desc', '')[:50]}",
            "save_path": str(save_dir),
            "aweme_id": key,
        }
    except Exception as e:
        return {"error": f"下载失败: {str(e)}"}


# ===================================================================
# Tool 9: download_user - 批量下载用户作品（异步）
# ===================================================================
@mcp.tool()
def download_user(
    url: str,
    save_path: str = "./downloads",
    mode: str = "post",
    number: int = 0,
    increase: bool = False,
    music: bool = True,
    cover: bool = True,
    avatar: bool = True,
    json_data: bool = True,
    folderstyle: bool = True,
    thread: int = 5,
    cookie: str = "",
    start_time: str = "",
    end_time: str = "",
) -> dict:
    """异步批量下载抖音用户主页的作品，立即返回任务ID

    Args:
        url: 用户主页分享链接
        save_path: 保存路径，默认 ./downloads
        mode: 下载模式 - post(发布)/like(喜欢)/mix(合集)，默认post
        number: 下载数量限制，0=全部
        increase: 是否增量更新
        music: 是否下载音乐
        cover: 是否下载封面
        avatar: 是否下载头像
        json_data: 是否保存JSON
        folderstyle: 文件夹风格
        thread: 下载线程数
        cookie: 自定义Cookie
        start_time: 开始时间 YYYY-MM-DD
        end_time: 结束时间 YYYY-MM-DD

    Returns:
        {"task_id": "xxx"} - 用 get_task_status 查询进度
    """
    task_id = _generate_task_id()

    def _worker():
        try:
            if cookie:
                douyin_headers["Cookie"] = cookie

            dy = Douyin(database=increase)
            dl = Download(
                headers=douyin_headers,
                folder_style=folderstyle,
                music=music,
                cover=cover,
                avatar=avatar,
                json_data=json_data,
                progress_bar=False,
                thread=thread,
            )

            share_url = dy.getShareLink(url)
            key_type, key = dy.getKey(share_url)

            if key_type != "user":
                with _task_lock:
                    _tasks[task_id]["status"] = "failed"
                    _tasks[task_id]["error"] = f"链接不是用户主页(type={key_type})"
                return

            # 获取用户信息
            user_data = dy.getUserDetailInfo(key)
            nickname = ""
            if user_data and user_data.get("user"):
                nickname = utils.replaceStr(user_data["user"]["nickname"])

            user_dir = Path(save_path) / f"user_{nickname}_{key}"
            user_dir.mkdir(parents=True, exist_ok=True)

            # 获取作品列表
            aweme_list = dy.getUserInfo(
                sec_uid=key,
                mode=mode,
                count=35,
                number=number,
                increase=increase,
                start_time=start_time,
                end_time=end_time,
            )

            if not aweme_list:
                with _task_lock:
                    _tasks[task_id]["status"] = "completed"
                    _tasks[task_id]["result"] = {"message": "未找到可下载的作品", "count": 0}
                return

            with _task_lock:
                _tasks[task_id]["progress"] = 10
                _tasks[task_id]["message"] = f"已获取 {len(aweme_list)} 个作品，开始下载..."

            # 执行下载
            mode_dir = user_dir / mode
            mode_dir.mkdir(exist_ok=True)
            success_count = dl.userDownload(awemeList=aweme_list, savePath=str(mode_dir))

            with _task_lock:
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["progress"] = 100
                _tasks[task_id]["result"] = {
                    "success_count": success_count,
                    "total": len(aweme_list),
                    "save_path": str(mode_dir),
                    "nickname": nickname,
                }

        except Exception as e:
            with _task_lock:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["error"] = str(e)

    # 注册任务
    with _task_lock:
        _tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "message": "任务已创建，正在解析链接...",
            "result": None,
            "error": None,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    # 异步执行
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    return {"task_id": task_id, "message": "任务已创建，使用 get_task_status 查询进度"}


# ===================================================================
# Tool 10: get_task_status - 查询异步任务状态
# ===================================================================
@mcp.tool()
def get_task_status(task_id: str) -> dict:
    """查询异步下载任务的状态和结果

    Args:
        task_id: 任务ID，由 download_user 等异步工具返回

    Returns:
        任务状态: status(running/completed/failed)、progress、result 等
    """
    with _task_lock:
        task = _tasks.get(task_id)
        if not task:
            return {"error": f"任务 {task_id} 不存在"}
        return dict(task)


# ===================================================================
# Tool 11: set_cookie - 设置/更新 Cookie
# ===================================================================
@mcp.tool()
def set_cookie(cookie: str) -> dict:
    """设置抖音请求的Cookie，用于解决登录态和权限问题

    Args:
        cookie: Cookie字符串，格式: "name1=value1; name2=value2;"
               关键字段: msToken, ttwid, odin_tt, passport_csrf_token, sid_guard

    Returns:
        设置结果
    """
    try:
        douyin_headers["Cookie"] = cookie
        return {"success": True, "message": "Cookie 已更新"}
    except Exception as e:
        return {"error": f"设置Cookie失败: {str(e)}"}


# ===================================================================
# Tool 12: resolve_and_download - 一键解析并下载（最常用）
# ===================================================================
@mcp.tool()
def resolve_and_download(
    url: str,
    save_path: str = "./downloads",
    music: bool = True,
    cover: bool = True,
    thread: int = 3,
    cookie: str = "",
    number: int = 0,
) -> dict:
    """自动识别链接类型并执行对应下载操作（一键下载）

    支持: 单个作品(同步下载)、用户主页(异步批量)、合集、音乐

    Args:
        url: 任意抖音分享链接
        save_path: 保存路径，默认 ./downloads
        music: 是否下载音乐
        cover: 是否下载封面
        thread: 下载线程数
        cookie: 自定义Cookie
        number: 下载数量限制(用户主页时有效)，0=全部

    Returns:
        下载结果或任务ID
    """
    try:
        if cookie:
            douyin_headers["Cookie"] = cookie

        dy = Douyin(database=False)
        share_url = dy.getShareLink(url)
        key_type, key = dy.getKey(share_url)

        if key_type is None:
            return {"error": "无法解析链接"}

        # 单个作品 - 同步下载
        if key_type == "aweme":
            return download(
                url=url, save_path=save_path, music=music, cover=cover, thread=thread
            )

        # 用户主页 - 异步批量
        if key_type == "user":
            return download_user(
                url=url, save_path=save_path, number=number,
                music=music, cover=cover, thread=thread
            )

        # 合集 - 异步下载
        if key_type == "mix":
            task_id = _generate_task_id()

            def _mix_worker():
                try:
                    dy_inner = Douyin(database=False)
                    dl = Download(
                        headers=douyin_headers, folder_style=True,
                        music=music, cover=cover, avatar=False,
                        json_data=True, progress_bar=False, thread=thread,
                    )
                    aweme_list = dy_inner.getMixInfo(mix_id=key, count=35, number=number)
                    if aweme_list:
                        mix_name = utils.replaceStr(aweme_list[0].get("mix_info", {}).get("mix_name", "unknown"))
                        mix_dir = Path(save_path) / f"mix_{mix_name}_{key}"
                        mix_dir.mkdir(parents=True, exist_ok=True)
                        success = dl.userDownload(awemeList=aweme_list, savePath=str(mix_dir))
                        with _task_lock:
                            _tasks[task_id]["status"] = "completed"
                            _tasks[task_id]["progress"] = 100
                            _tasks[task_id]["result"] = {"success_count": success, "total": len(aweme_list), "save_path": str(mix_dir)}
                    else:
                        with _task_lock:
                            _tasks[task_id]["status"] = "completed"
                            _tasks[task_id]["result"] = {"message": "合集为空", "count": 0}
                except Exception as e:
                    with _task_lock:
                        _tasks[task_id]["status"] = "failed"
                        _tasks[task_id]["error"] = str(e)

            with _task_lock:
                _tasks[task_id] = {"status": "running", "progress": 0, "message": f"正在下载合集 {key}...", "result": None, "error": None, "start_time": time.strftime("%Y-%m-%d %H:%M:%S")}
            threading.Thread(target=_mix_worker, daemon=True).start()
            return {"task_id": task_id, "key_type": "mix", "message": "合集下载任务已创建"}

        # 音乐 - 异步下载
        if key_type == "music":
            task_id = _generate_task_id()

            def _music_worker():
                try:
                    dy_inner = Douyin(database=False)
                    dl = Download(
                        headers=douyin_headers, folder_style=True,
                        music=music, cover=cover, avatar=False,
                        json_data=True, progress_bar=False, thread=thread,
                    )
                    aweme_list = dy_inner.getMusicInfo(music_id=key, count=35, number=number)
                    if aweme_list:
                        music_title = utils.replaceStr(aweme_list[0].get("music", {}).get("title", "unknown"))
                        music_dir = Path(save_path) / f"music_{music_title}_{key}"
                        music_dir.mkdir(parents=True, exist_ok=True)
                        success = dl.userDownload(awemeList=aweme_list, savePath=str(music_dir))
                        with _task_lock:
                            _tasks[task_id]["status"] = "completed"
                            _tasks[task_id]["progress"] = 100
                            _tasks[task_id]["result"] = {"success_count": success, "total": len(aweme_list), "save_path": str(music_dir)}
                    else:
                        with _task_lock:
                            _tasks[task_id]["status"] = "completed"
                            _tasks[task_id]["result"] = {"message": "音乐下无作品", "count": 0}
                except Exception as e:
                    with _task_lock:
                        _tasks[task_id]["status"] = "failed"
                        _tasks[task_id]["error"] = str(e)

            with _task_lock:
                _tasks[task_id] = {"status": "running", "progress": 0, "message": f"正在下载音乐 {key} 下的作品...", "result": None, "error": None, "start_time": time.strftime("%Y-%m-%d %H:%M:%S")}
            threading.Thread(target=_music_worker, daemon=True).start()
            return {"task_id": task_id, "key_type": "music", "message": "音乐下载任务已创建"}

        # 直播 - 仅返回信息
        if key_type == "live":
            return get_live_info(web_rid=key)

        return {"error": f"不支持的链接类型: {key_type}"}

    except Exception as e:
        return {"error": f"解析下载失败: {str(e)}"}


# ===================================================================
# 入口
# ===================================================================
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Douyin MCP Server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio"],
        help="MCP transport to use. Currently only stdio is supported.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

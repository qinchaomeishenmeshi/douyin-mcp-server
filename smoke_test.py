#!/usr/bin/env python3
"""Optional real-network smoke test for the Douyin MCP server."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import server


def _print_json(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Douyin MCP smoke test")
    parser.add_argument(
        "--share-url",
        help="A Douyin share URL to validate with parse_link and get_video_info.",
    )
    parser.add_argument(
        "--cookie",
        help="Cookie string to pass to set_cookie before running network checks.",
    )
    parser.add_argument(
        "--cookie-env",
        default="DOUYIN_COOKIE",
        help="Environment variable name to read the cookie from when --cookie is omitted.",
    )
    parser.add_argument(
        "--skip-video-info",
        action="store_true",
        help="Only run set_cookie and parse_link. Skip get_video_info.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any step returns an MCP error payload.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.share_url:
        parser.print_help()
        return 0

    cookie = args.cookie or os.environ.get(args.cookie_env, "")

    if cookie:
        cookie_result = server.set_cookie(cookie)
        _print_json("set_cookie", cookie_result)
        if args.strict and cookie_result.get("error"):
            return 1

    parse_result = server.parse_link(args.share_url)
    _print_json("parse_link", parse_result)
    if args.strict and parse_result.get("error"):
        return 1

    if args.skip_video_info:
        return 0

    key_type = parse_result.get("key_type")
    key = parse_result.get("key")
    if key_type != "aweme" or not key:
        print("\nSkipping get_video_info because the parsed target is not a single aweme.")
        return 0 if not args.strict else 1

    info_result = server.get_video_info(key)
    _print_json("get_video_info", info_result)
    if args.strict and info_result.get("error"):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

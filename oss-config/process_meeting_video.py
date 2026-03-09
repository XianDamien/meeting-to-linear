#!/usr/bin/env python3
"""
处理会议视频：转录会议录音/视频

默认模式：本地文件直接转录（flash 模型），无需 OSS
可选模式：加 --use-oss 走 OSS 上传 + filetrans 转录
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载配置
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)


def process_local(video_path: Path, output_dir: Path):
    """使用 flash 模型直接转录本地文件"""
    from qwen_asr import load_api_key, process_file

    api_key = load_api_key(env_path)

    print("\n[1/1] 转录本地文件...")
    success = process_file(
        file_path=video_path,
        api_key=api_key,
        output_dir=output_dir,
        save_srt=True,
    )

    if not success:
        raise RuntimeError("转录失败")

    print(f"\n转录完成! 文件保存在: {output_dir / video_path.stem}")


def process_with_oss(video_path: Path, output_dir: Path):
    """上传到 OSS 后使用 filetrans 模型转录"""
    from upload_to_oss import upload_video_to_oss
    from qwen_asr import load_api_key, process_url_filetrans

    api_key = load_api_key(env_path)

    # Step 1: 上传到 OSS
    print("\n[1/2] 上传视频到 OSS...")
    public_url = upload_video_to_oss(str(video_path))

    # 保存 URL
    url_file = output_dir / 'video-url.txt'
    with open(url_file, 'w') as f:
        f.write(f"{public_url}\n")
    print(f"URL 已保存到: {url_file}")

    # Step 2: 转录
    print("\n[2/2] 转录视频...")
    success = process_url_filetrans(
        audio_url=public_url,
        api_key=api_key,
        output_dir=output_dir,
        save_srt=True,
    )

    if not success:
        raise RuntimeError("转录失败")

    print(f"\n视频 URL: {public_url}")


def process_meeting_video(video_path: str, output_dir: str = None, use_oss: bool = False):
    """
    完整处理流程

    Args:
        video_path: 本地视频文件路径
        output_dir: 输出目录（默认为视频所在目录）
        use_oss: 是否使用 OSS 上传模式
    """
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    if output_dir is None:
        output_dir = video_path.parent

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    if use_oss:
        print("会议视频处理流程（OSS 上传 + filetrans 转录）")
    else:
        print("会议视频处理流程（本地直接转录）")
    print("=" * 60)

    if use_oss:
        process_with_oss(video_path, output_dir)
    else:
        process_local(video_path, output_dir)

    print("\n" + "=" * 60)
    print("处理完成!")
    print(f"转录文件: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='处理会议视频（转录，可选上传 OSS）')
    parser.add_argument('video', help='视频文件路径')
    parser.add_argument('--output', help='输出目录（默认为视频所在目录）')
    parser.add_argument('--use-oss', action='store_true',
                        help='使用 OSS 上传模式（需要 OSS 凭证配置）')
    args = parser.parse_args()

    try:
        process_meeting_video(args.video, args.output, args.use_oss)
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)

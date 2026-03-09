#!/usr/bin/env python3
"""
处理会议视频：上传到 OSS + 使用 filetrans 转录
"""
import os
import sys
import subprocess
from pathlib import Path
from upload_to_oss import upload_video_to_oss, load_oss_config
from dotenv import load_dotenv

# 加载配置
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

def transcribe_video_url(public_url: str, output_dir: str):
    """
    使用 qwen-asr filetrans 模式转录视频 URL

    Args:
        public_url: 视频的 public URL
        output_dir: 转录文件输出目录
    """
    dashscope_key = os.getenv('DASHSCOPE_API_KEY')
    if not dashscope_key:
        raise ValueError("缺少 DASHSCOPE_API_KEY 配置")

    print(f"\n开始转录视频: {public_url}")

    # 调用 qwen-asr-transcriber
    cmd = [
        'uv', 'run',
        os.path.expanduser('~/.claude/skills/qwen-asr-transcriber/scripts/qwen_asr.py'),
        '--model', 'filetrans',
        '--url', public_url,
        '--output', output_dir,
        '--srt'  # 同时生成 SRT 字幕
    ]

    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"转录失败: {result.stderr}")

    print(f"✅ 转录完成! 文件保存在: {output_dir}")

def process_meeting_video(video_path: str, output_dir: str = None):
    """
    完整处理流程

    Args:
        video_path: 本地视频文件路径
        output_dir: 输出目录（默认为视频所在目录）
    """
    video_path = Path(video_path).resolve()
    if output_dir is None:
        output_dir = video_path.parent

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("会议视频处理流程")
    print("=" * 60)

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
    transcribe_video_url(public_url, str(output_dir))

    print("\n" + "=" * 60)
    print("✅ 处理完成!")
    print(f"视频 URL: {public_url}")
    print(f"转录文件: {output_dir}")
    print("=" * 60)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='处理会议视频（上传 + 转录）')
    parser.add_argument('video', help='视频文件路径')
    parser.add_argument('--output', help='输出目录（默认为视频所在目录）')
    args = parser.parse_args()

    try:
        process_meeting_video(args.video, args.output)
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)

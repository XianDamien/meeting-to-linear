#!/usr/bin/env python3
"""
上传会议视频到 OSS 并返回 public URL
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import oss2
from dotenv import load_dotenv

# 加载配置
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

def load_oss_config():
    """加载 OSS 配置"""
    config = {
        'access_key_id': os.getenv('OSS_ACCESS_KEY_ID'),
        'access_key_secret': os.getenv('OSS_ACCESS_KEY_SECRET'),
        'endpoint': os.getenv('OSS_ENDPOINT'),
        'bucket_name': os.getenv('OSS_BUCKET_NAME'),
        'public_base_url': os.getenv('OSS_PUBLIC_BASE_URL'),
    }

    # 验证配置
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(f"缺少 OSS 配置: {', '.join(missing)}")

    return config

def upload_video_to_oss(video_path: str, folder: str = 'meetings') -> str:
    """
    上传视频到 OSS

    Args:
        video_path: 本地视频文件路径
        folder: OSS 存储文件夹（默认 meetings）

    Returns:
        public_url: 视频的 public URL
    """
    config = load_oss_config()

    # 初始化 OSS 客户端
    auth = oss2.Auth(config['access_key_id'], config['access_key_secret'])
    bucket = oss2.Bucket(auth, config['endpoint'], config['bucket_name'])

    # 生成 OSS 文件路径: meetings/YYYYMMDD/filename.mp4
    video_name = Path(video_path).name
    date_str = datetime.now().strftime('%Y%m%d')
    object_key = f"{folder}/{date_str}/{video_name}"

    # 上传文件（带进度条）
    print(f"上传 {video_name} 到 OSS...")
    total_size = os.path.getsize(video_path)

    def progress_callback(consumed_bytes, total_bytes):
        if total_bytes:
            percentage = 100 * consumed_bytes / total_bytes
            print(f'\r上传进度: {percentage:.1f}% ({consumed_bytes}/{total_bytes} bytes)', end='')

    bucket.put_object_from_file(
        object_key,
        video_path,
        progress_callback=progress_callback
    )
    print()  # 换行

    # 构建 public URL
    public_url = f"{config['public_base_url']}/{object_key}"

    print(f"✅ 上传成功!")
    print(f"Public URL: {public_url}")

    return public_url

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='上传视频到 OSS')
    parser.add_argument('video', help='视频文件路径')
    parser.add_argument('--folder', default='meetings', help='OSS 存储文件夹（默认 meetings）')
    parser.add_argument('--output', help='输出 URL 到文件')
    args = parser.parse_args()

    try:
        public_url = upload_video_to_oss(args.video, args.folder)

        # 保存到文件
        if args.output:
            with open(args.output, 'w') as f:
                f.write(f"{public_url}\n")
            print(f"URL 已保存到: {args.output}")
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)

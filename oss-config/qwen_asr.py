#!/usr/bin/env python3
"""
Qwen ASR Transcriber - Batch audio/video transcription using Qwen3-ASR-Flash
With VAD-based segmentation for accurate SRT timestamps.

Usage:
    uv run qwen_asr.py <file_or_folder>
"""

import os
import sys
import io
import json
import argparse
import shutil
import tempfile
import subprocess
import time
import traceback
import random
import concurrent.futures
from pathlib import Path
from datetime import datetime, timedelta

import srt
import librosa
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from tqdm import tqdm
from pydub import AudioSegment
from silero_vad import load_silero_vad, get_speech_timestamps

import dashscope
from dashscope import MultiModalConversation
from dashscope.audio.qwen_asr import QwenTranscription

try:
    import oss2
    HAS_OSS = True
except ImportError:
    HAS_OSS = False

import requests
from urllib.parse import urlparse

# Constants
SCRIPT_DIR = Path(__file__).parent
GLOBAL_ENV_PATH = Path.home() / ".qwen_services" / ".env"  # Global config (preferred)
LOCAL_ENV_PATH = SCRIPT_DIR.parent / ".env"  # Local fallback
QWEN_CONFIG_PATH = Path.home() / ".qwen" / "config"  # Qwen config (for OSS)
WAV_SAMPLE_RATE = 16000
MAX_API_RETRY = 5
API_RETRY_SLEEP = (1, 2)

# Supported file extensions
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.opus', '.amr', '.wma'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.mpeg', '.wmv'}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def load_api_key(env_path: Path | None = None) -> str:
    """Load DASHSCOPE_API_KEY from .env file

    Search order:
    1. Explicitly provided env_path
    2. Global config: ~/.qwen_services/.env (preferred)
    3. Local config: <skill_dir>/.env (fallback)
    """
    # Determine which env file to use
    if env_path and env_path.exists():
        target_env = env_path
    elif GLOBAL_ENV_PATH.exists():
        target_env = GLOBAL_ENV_PATH
    elif LOCAL_ENV_PATH.exists():
        target_env = LOCAL_ENV_PATH
    else:
        print(f"Error: No .env file found")
        print(f"\nSetup instructions:")
        print(f"1. Create global config directory: mkdir -p ~/.qwen_services")
        print(f"2. Create .env file: touch ~/.qwen_services/.env")
        print(f"3. Add your API key: echo 'DASHSCOPE_API_KEY=your_key_here' >> ~/.qwen_services/.env")
        print(f"4. Get API key from: https://dashscope.console.aliyun.com/apiKey")
        sys.exit(1)

    load_dotenv(target_env)
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print(f"Error: DASHSCOPE_API_KEY not found in {target_env}")
        print(f"Add this line to {target_env}:")
        print(f"DASHSCOPE_API_KEY=your_key_here")
        sys.exit(1)

    print(f"Using config: {target_env}")
    return api_key


def load_oss_config() -> dict:
    """Load OSS configuration from ~/.qwen/config"""
    if not QWEN_CONFIG_PATH.exists():
        raise FileNotFoundError(f"OSS config not found at {QWEN_CONFIG_PATH}")

    config = {}
    with open(QWEN_CONFIG_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('"')

    required = ['OSS_ACCESS_KEY_ID', 'OSS_ACCESS_KEY_SECRET', 'OSS_ENDPOINT', 'OSS_BUCKET_NAME']
    missing = [k for k in required if k not in config]
    if missing:
        raise ValueError(f"Missing OSS config keys: {missing}")

    return config


def download_from_url(url: str, output_path: Path) -> None:
    """Download audio file from URL"""
    print(f"  Downloading from URL...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    with open(output_path, 'wb') as f:
        if total_size == 0:
            f.write(response.content)
        else:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                progress = (downloaded / total_size) * 100
                print(f"\r  Progress: {progress:.1f}%", end='', flush=True)
            print()  # New line after progress


def upload_to_oss(local_path: Path, oss_key: str, config: dict, expire_seconds: int = 7200) -> str:
    """Upload file to OSS and return a signed URL (works with private buckets)"""
    if not HAS_OSS:
        raise ImportError("oss2 library not installed. Run: uv pip install oss2")

    print(f"  Uploading to OSS...")

    auth = oss2.Auth(config['OSS_ACCESS_KEY_ID'], config['OSS_ACCESS_KEY_SECRET'])
    endpoint = config['OSS_ENDPOINT'].strip()
    bucket_name = config['OSS_BUCKET_NAME'].strip()
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # Upload file
    with open(local_path, 'rb') as f:
        bucket.put_object(oss_key, f)

    # Generate signed URL for private bucket access (expires in expire_seconds)
    signed_url = bucket.sign_url('GET', oss_key, expire_seconds)

    print(f"  OSS signed URL (expires in {expire_seconds}s): {signed_url[:80]}...")
    return signed_url


def load_audio(file_path: str) -> np.ndarray:
    """Load audio file and convert to 16kHz mono"""
    try:
        wav_data, _ = librosa.load(file_path, sr=WAV_SAMPLE_RATE, mono=True)
        return wav_data
    except Exception as e:
        # Fallback to ffmpeg
        try:
            command = [
                'ffmpeg', '-i', file_path,
                '-ar', str(WAV_SAMPLE_RATE),
                '-ac', '1',
                '-c:a', 'pcm_s16le',
                '-f', 'wav', '-'
            ]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout_data, stderr_data = process.communicate()
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg error: {stderr_data.decode('utf-8', errors='ignore')}")
            with io.BytesIO(stdout_data) as data_io:
                wav_data, _ = sf.read(data_io, dtype='float32')
            return wav_data
        except Exception as ffmpeg_e:
            raise RuntimeError(f"Failed to load audio: {ffmpeg_e}")


def get_adaptive_segment_params(duration_s: float, user_threshold: int = None, user_max: int = None) -> tuple[int, int]:
    """
    Calculate optimal segment parameters based on audio duration.
    Returns (segment_threshold, max_segment) in seconds.

    Duration-based strategy:
    - < 5 min: 10-25s (sentence-level precision)
    - 5-15 min: 20-40s (balanced)
    - 15-30 min: 30-60s (paragraph-level)
    - 30-60 min: 40-80s (efficient processing)
    - > 60 min: 60-120s (large chunks for long audio)
    """
    # If user explicitly set parameters, respect them
    if user_threshold is not None and user_max is not None:
        return (user_threshold, user_max)

    duration_minutes = duration_s / 60

    if duration_minutes < 5:
        # Short audio: precise sentence-level segmentation
        threshold, max_seg = 10, 25
    elif duration_minutes < 15:
        # Medium-short audio: balanced segmentation
        threshold, max_seg = 20, 40
    elif duration_minutes < 30:
        # Medium audio: paragraph-level chunks
        threshold, max_seg = 30, 60
    elif duration_minutes < 60:
        # Long audio: efficient chunks
        threshold, max_seg = 40, 80
    else:
        # Very long audio: large chunks
        threshold, max_seg = 60, 120

    # Apply user overrides if provided
    if user_threshold is not None:
        threshold = user_threshold
    if user_max is not None:
        max_seg = user_max

    return (threshold, max_seg)


def process_vad(wav: np.ndarray, vad_model, segment_threshold_s: int = 10, max_segment_threshold_s: int = 25,
                min_silence_ms: int = 800) -> list[tuple[int, int, np.ndarray]]:
    """Segment audio using VAD"""
    try:
        vad_params = {
            'sampling_rate': WAV_SAMPLE_RATE,
            'return_seconds': False,
            'min_speech_duration_ms': 1500,
            'min_silence_duration_ms': min_silence_ms
        }
        speech_timestamps = get_speech_timestamps(wav, vad_model, **vad_params)

        if not speech_timestamps:
            raise ValueError("No speech segments detected by VAD.")

        # Find split points based on speech boundaries
        potential_split_points = {0.0, len(wav)}
        for ts in speech_timestamps:
            potential_split_points.add(ts['start'])
        sorted_splits = sorted(potential_split_points)

        # Create segments based on threshold
        final_split_points = {0.0, len(wav)}
        segment_threshold_samples = segment_threshold_s * WAV_SAMPLE_RATE
        target_time = segment_threshold_samples
        while target_time < len(wav):
            closest_point = min(sorted_splits, key=lambda p: abs(p - target_time))
            final_split_points.add(closest_point)
            target_time += segment_threshold_samples
        final_ordered_splits = sorted(final_split_points)

        # Ensure no segment exceeds max threshold
        max_segment_samples = max_segment_threshold_s * WAV_SAMPLE_RATE
        new_split_points = [0.0]
        for i in range(1, len(final_ordered_splits)):
            start = final_ordered_splits[i - 1]
            end = final_ordered_splits[i]
            segment_length = end - start
            if segment_length <= max_segment_samples:
                new_split_points.append(end)
            else:
                num_subsegments = int(np.ceil(segment_length / max_segment_samples))
                subsegment_length = segment_length / num_subsegments
                for j in range(1, num_subsegments):
                    new_split_points.append(start + j * subsegment_length)
                new_split_points.append(end)

        # Create segment list
        segments = []
        for i in range(len(new_split_points) - 1):
            start_sample = int(new_split_points[i])
            end_sample = int(new_split_points[i + 1])
            segments.append((start_sample, end_sample, wav[start_sample:end_sample]))
        return segments

    except Exception as e:
        # Fallback: split by max threshold
        segments = []
        total_samples = len(wav)
        max_chunk_samples = max_segment_threshold_s * WAV_SAMPLE_RATE
        for start in range(0, total_samples, max_chunk_samples):
            end = min(start + max_chunk_samples, total_samples)
            if end > start:
                segments.append((start, end, wav[start:end]))
        return segments


def save_audio_segment(wav: np.ndarray, file_path: str):
    """Save audio segment to file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    sf.write(file_path, wav, WAV_SAMPLE_RATE)


def transcribe_segment(wav_path: str, api_key: str, context: str = "") -> tuple[str, str]:
    """Transcribe a single audio segment"""
    # Convert to mp3 if file > 10MB
    file_size = os.path.getsize(wav_path)
    if file_size > 10 * 1024 * 1024:
        mp3_path = os.path.splitext(wav_path)[0] + ".mp3"
        audio = AudioSegment.from_file(wav_path)
        audio.export(mp3_path, format="mp3")
        wav_path = mp3_path

    file_url = f"file://{wav_path}"

    for retry in range(MAX_API_RETRY):
        try:
            messages = [
                {"role": "system", "content": [{"text": context}]},
                {"role": "user", "content": [{"audio": file_url}]}
            ]
            response = MultiModalConversation.call(
                api_key=api_key,
                model="qwen3-asr-flash",
                messages=messages,
                result_format="message",
                asr_options={"enable_lid": True, "enable_itn": True}
            )

            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code}")

            output = response['output']['choices'][0]
            text = ""
            if output["message"]["content"]:
                text = output["message"]["content"][0].get("text", "")

            lang_code = None
            if "annotations" in output["message"]:
                lang_code = output["message"]["annotations"][0].get("language")

            return lang_code or "unknown", text

        except Exception as e:
            if retry < MAX_API_RETRY - 1:
                time.sleep(random.uniform(*API_RETRY_SLEEP))
            else:
                print(f"  Failed after {MAX_API_RETRY} retries: {e}")
                return "unknown", ""


def transcribe_url_filetrans(audio_url: str, api_key: str, enable_words: bool = True, enable_itn: bool = True) -> dict:
    """Transcribe audio from URL using qwen3-asr-flash-filetrans (async, up to 12 hours)"""
    print(f"  Submitting transcription task for URL: {audio_url}")

    # Submit async transcription task
    # Note: According to the API docs, the parameter is file_urls (list) for batch, or file_url (str) for single
    task_response = QwenTranscription.call(
        api_key=api_key,
        model='qwen3-asr-flash-filetrans',
        file_url=audio_url,  # Single URL (not a list)
        enable_itn=enable_itn,
        enable_words=enable_words
    )

    if task_response.status_code != 200:
        raise Exception(f"Failed to submit task: {task_response.status_code}")

    task_id = task_response.output.task_id
    print(f"  Task ID: {task_id}")
    print(f"  Waiting for transcription to complete...")

    # Wait for task completion (polls automatically)
    task_result = QwenTranscription.wait(task=task_id)

    # Check task status
    output = task_result.output
    print(f"  Task status: {output.get('task_status')}")

    if output.get('task_status') == 'FAILED':
        error_code = output.get('code', 'UNKNOWN')
        error_msg = output.get('message', 'Unknown error')
        raise Exception(f"Transcription task failed: {error_code} - {error_msg}")

    if task_result.status_code != 200:
        raise Exception(f"Task failed with status code: {task_result.status_code}")

    # The filetrans API returns output.result.transcription_url - a URL to download JSON results
    # JSON structure: { file_url, audio_info, transcripts: [{ channel_id, text, sentences: [{ begin_time, end_time, text, words, language }] }] }
    result_obj = output.get('result')
    if not result_obj or not isinstance(result_obj, dict):
        raise Exception(f"No result in response. Output keys: {list(output.keys())}")

    tx_url = result_obj.get('transcription_url')
    if not tx_url:
        raise Exception(f"No transcription_url in result. Result keys: {list(result_obj.keys())}")

    print(f"  Fetching transcription results...")
    resp = requests.get(tx_url, timeout=60)
    resp.raise_for_status()
    tx_data = resp.json()

    # Extract audio_info if available (duration, sample rate, etc.)
    audio_info = tx_data.get('audio_info', {})

    # Parse the transcripts array
    transcripts_list = tx_data.get('transcripts', [])
    if not transcripts_list:
        raise Exception(f"Empty transcripts in response. Keys: {list(tx_data.keys())}")

    channel = transcripts_list[0]  # First channel (mono audio)
    full_text = channel.get('text', '')
    sentences = channel.get('sentences', [])

    # Detect language from first sentence
    language = "unknown"
    if sentences:
        language = sentences[0].get('language', 'unknown')

    # Extract sentence-level data (for SRT) and word-level data
    sentences_data = []
    words_data = []
    for s in sentences:
        sentences_data.append({
            'text': s.get('text', ''),
            'start_time': s.get('begin_time', 0),  # milliseconds
            'end_time': s.get('end_time', 0),
            'language': s.get('language', ''),
        })
        if enable_words:
            for w in s.get('words', []):
                words_data.append({
                    'text': w.get('text', ''),
                    'start_time': w.get('begin_time', 0),
                    'end_time': w.get('end_time', 0)
                })

    return {
        'language': language,
        'text': full_text,
        'sentences': sentences_data,
        'words': words_data,
        'audio_info': audio_info,
    }


def process_url_filetrans(audio_url: str, api_key: str, output_dir: Path,
                          save_srt: bool = False, enable_words: bool = True,
                          upload_to_oss_flag: bool = False) -> bool:
    """Process URL using filetrans model

    Args:
        audio_url: URL to audio file
        api_key: DashScope API key
        output_dir: Output directory
        save_srt: Save SRT file
        enable_words: Enable word-level timestamps
        upload_to_oss_flag: If True, download URL and upload to OSS first
    """
    print(f"Processing URL with filetrans model")

    final_url = audio_url
    oss_url = None
    temp_file = None
    oss_config = None

    try:
        # If upload_to_oss is enabled, download and upload first
        if upload_to_oss_flag:
            print(f"📤 OSS upload mode enabled")

            # Load OSS config
            oss_config = load_oss_config()

            # Download to temp file
            temp_file = Path(tempfile.mkdtemp()) / f"audio_{int(time.time())}.mp3"
            download_from_url(audio_url, temp_file)

            # Upload to OSS
            oss_key = f"transcription/{temp_file.name}"
            oss_url = upload_to_oss(temp_file, oss_key, oss_config)
            final_url = oss_url

            print(f"✅ Using OSS URL for transcription")

        # Transcribe
        result = transcribe_url_filetrans(final_url, api_key, enable_words=enable_words)

        print(f"  Language detected: {result['language']}")
        print(f"  Text length: {len(result['text'])} characters")
        print(f"  Sentences: {len(result.get('sentences', []))}")
        print(f"  Words with timestamps: {len(result.get('words', []))}")

        # Generate filename from URL and create subfolder
        parsed = urlparse(audio_url)
        filename = Path(parsed.path).stem or 'transcription'
        subfolder = output_dir / filename
        subfolder.mkdir(parents=True, exist_ok=True)

        # Save TXT
        txt_path = subfolder / f"{filename}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result['text'])
        print(f"  Saved: {txt_path}")

        # Save JSON with sentence-level timestamps
        json_path = subfolder / f"{filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'language': result['language'],
                'text': result['text'],
                'sentences': result.get('sentences', [])
            }, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {json_path}")

        # Save SRT using sentence-level timestamps (much more accurate than word grouping)
        if save_srt and result.get('sentences'):
            subtitles = []
            for s in result['sentences']:
                text = s['text'].strip()
                if text:
                    subtitles.append(srt.Subtitle(
                        index=len(subtitles) + 1,
                        start=timedelta(milliseconds=s['start_time']),
                        end=timedelta(milliseconds=s['end_time']),
                        content=text
                    ))

            srt_path = subfolder / f"{filename}.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subtitles))
            print(f"  Saved: {srt_path}")

        # Save meta.json
        meta = {
            'source_url': audio_url,
            'model': 'qwen3-asr-flash-filetrans',
            'transcription_date': datetime.now().isoformat(timespec='seconds'),
            'language': result['language'],
            'text_length': len(result['text']),
            'sentence_count': len(result.get('sentences', [])),
            'word_count': len(result['text'].split()),
        }
        if oss_url:
            meta['oss_url'] = oss_url
        if result.get('audio_info'):
            meta['audio_info'] = result['audio_info']
        meta_path = subfolder / 'meta.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {meta_path}")

        return True

    except Exception as e:
        print(f"  Error: {e}")
        traceback.print_exc()
        return False

    finally:
        # Cleanup temp file if it was created
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
                if temp_file.parent.name.startswith('tmp'):
                    shutil.rmtree(temp_file.parent, ignore_errors=True)
            except Exception as e:
                print(f"  Warning: Failed to cleanup temp file: {e}")


def process_file(file_path: Path, api_key: str, output_dir: Path | None = None,
                 context: str = "", num_threads: int = 4, save_srt: bool = False,
                 segment_threshold_s: int = 10, max_segment_threshold_s: int = 25,
                 min_silence_ms: int = 800) -> bool:
    """Process a single file with VAD segmentation"""
    print(f"Processing: {file_path.name}")

    # Load audio
    try:
        wav = load_audio(str(file_path))
        duration_s = len(wav) / WAV_SAMPLE_RATE
        duration_minutes = duration_s / 60
        print(f"  Duration: {duration_s:.2f}s ({duration_minutes:.1f} minutes)")
    except Exception as e:
        print(f"  Failed to load audio: {e}")
        return False

    # Auto-adjust segment parameters based on duration (if using defaults)
    original_threshold = segment_threshold_s
    original_max = max_segment_threshold_s
    using_defaults = (segment_threshold_s == 10 and max_segment_threshold_s == 25)

    if using_defaults:
        # User didn't specify custom parameters, use adaptive strategy
        segment_threshold_s, max_segment_threshold_s = get_adaptive_segment_params(duration_s)
        if segment_threshold_s != original_threshold:
            print(f"  📊 Auto-adjusted segmentation for {duration_minutes:.1f} min audio:")
            print(f"     Target: {segment_threshold_s}s (was {original_threshold}s)")
            print(f"     Max: {max_segment_threshold_s}s (was {original_max}s)")
            estimated_segments = int(duration_s / segment_threshold_s)
            print(f"     Expected ~{estimated_segments} segments")
    else:
        # User specified custom parameters, respect them
        print(f"  Using custom parameters: threshold={segment_threshold_s}s, max={max_segment_threshold_s}s")
        estimated_segments = int(duration_s / segment_threshold_s)
        print(f"  Expected ~{estimated_segments} segments")

    # Check if this is long audio and suggest larger segments
    if duration_s > 3600 and segment_threshold_s < 30:  # > 1 hour and using small segments
        estimated_segments = int(duration_s / segment_threshold_s)
        print(f"  ⚠️  Long audio detected ({duration_minutes:.1f} minutes)")
        print(f"  Current settings will create ~{estimated_segments} segments")
        print(f"  For long audio, consider using: --segment-threshold 60 --max-segment 120")
        print(f"  This would create ~{int(duration_s / 60)} segments instead")
        response = input("  Continue with current settings? (y/n): ").strip().lower()
        if response != 'y':
            print("  Aborted. Please re-run with --segment-threshold 60 --max-segment 120")
            return False

    # Create temp directory for segments
    tmp_dir = Path(tempfile.mkdtemp())

    try:
        # Always use VAD for segmentation
        print(f"  Segmenting with VAD...")
        vad_model = load_silero_vad(onnx=True)
        segments = process_vad(wav, vad_model, segment_threshold_s, max_segment_threshold_s, min_silence_ms)
        print(f"  Created {len(segments)} segments")

        # Save segments to temp files
        segment_paths = []
        for idx, (start, end, segment_wav) in enumerate(segments):
            seg_path = tmp_dir / f"segment_{idx}.wav"
            save_audio_segment(segment_wav, str(seg_path))
            segment_paths.append((idx, start, end, str(seg_path)))

        # Transcribe segments in parallel
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {
                executor.submit(transcribe_segment, path, api_key, context): (idx, start, end)
                for idx, start, end, path in segment_paths
            }
            for future in tqdm(concurrent.futures.as_completed(futures),
                             total=len(futures), desc="  Transcribing", leave=False):
                idx, start, end = futures[future]
                lang, text = future.result()
                results.append((idx, start, end, lang, text))

        # Sort by index
        results.sort(key=lambda x: x[0])

        # Build full text
        full_text = " ".join(text for _, _, _, _, text in results if text)

        # Build SRT subtitles
        subtitles = []
        for idx, (_, start, end, _, text) in enumerate(results):
            if text:
                start_time = timedelta(seconds=start / WAV_SAMPLE_RATE)
                end_time = timedelta(seconds=end / WAV_SAMPLE_RATE)
                subtitles.append(srt.Subtitle(
                    index=idx + 1,
                    start=start_time,
                    end=end_time,
                    content=text
                ))

        # Determine output directory and create subfolder
        if output_dir is None:
            output_dir = file_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        subfolder = output_dir / file_path.stem
        subfolder.mkdir(parents=True, exist_ok=True)

        # Save SRT (only if requested)
        if save_srt:
            srt_path = subfolder / f"{file_path.stem}.srt"
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subtitles))
            print(f"  Saved: {srt_path}")

        # Save TXT
        txt_path = subfolder / f"{file_path.stem}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"  Saved: {txt_path}")

        # Save meta.json
        meta = {
            'source_file': str(file_path),
            'model': 'qwen3-asr-flash',
            'transcription_date': datetime.now().isoformat(timespec='seconds'),
            'duration_seconds': round(duration_s, 1),
            'segment_count': len(segments),
            'segment_params': {
                'threshold_s': segment_threshold_s,
                'max_s': max_segment_threshold_s,
            },
        }
        meta_path = subfolder / 'meta.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {meta_path}")

        return True

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def find_media_files(folder: Path) -> list[Path]:
    """Find all supported audio/video files in folder"""
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def main():
    parser = argparse.ArgumentParser(
        description='Batch transcribe audio/video files using Qwen3-ASR models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Models:
  flash (default)    - qwen3-asr-flash: For short audio (<5 min), local file processing with VAD
  filetrans          - qwen3-asr-flash-filetrans: For long audio (up to 12h), requires public URL

Examples:
  # Short audio with VAD segmentation (flash model)
  uv run qwen_asr.py audio.mp3

  # Long audio from URL (filetrans model, saves to ~/Downloads/transcripts)
  uv run qwen_asr.py --model filetrans --url "https://example.com/long_audio.mp3"

  # With SRT subtitles (saves to ~/Downloads/transcripts)
  uv run qwen_asr.py --model filetrans --url "https://bbc.co.uk/audio.mp3" --srt
        """
    )
    parser.add_argument('path', nargs='?', help='Path to audio/video file or folder (required for flash model)')
    parser.add_argument('--model', choices=['flash', 'filetrans'], default='flash',
                        help='Model to use: flash (default, local files) or filetrans (URL, long audio)')
    parser.add_argument('--url', help='Public URL to audio file (required for filetrans model)')
    parser.add_argument('--upload-oss', action='store_true',
                        help='Download URL and upload to OSS first (filetrans only, useful for inaccessible URLs)')
    parser.add_argument('--output', help='Output directory (default: same as input for flash, ./output for filetrans)')
    parser.add_argument('--context', default='', help='Context for better recognition (flash model only)')
    parser.add_argument('--threads', type=int, default=4, help='Number of parallel threads (flash model only)')
    parser.add_argument('--env', type=Path, default=GLOBAL_ENV_PATH, help='Path to .env file')
    parser.add_argument('--srt', action='store_true', help='Also output SRT subtitle file')
    parser.add_argument('--segment-threshold', type=int, default=10,
                        help='Target segment length in seconds (flash model only, default: 10s)')
    parser.add_argument('--max-segment', type=int, default=25,
                        help='Maximum segment length in seconds (flash model only, default: 25s)')
    parser.add_argument('--min-silence', type=int, default=800,
                        help='Minimum silence duration in ms (flash model only, default: 800ms)')

    args = parser.parse_args()

    # Load API key
    api_key = load_api_key(args.env)
    print(f"API key loaded")

    # Handle filetrans model (URL mode)
    if args.model == 'filetrans':
        if not args.url:
            print("Error: --url is required for filetrans model")
            print("Example: uv run qwen_asr.py --model filetrans --url 'https://example.com/audio.mp3'")
            sys.exit(1)

        output_dir = Path(args.output) if args.output else Path('~/Downloads/transcripts').expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        success = process_url_filetrans(args.url, api_key, output_dir, args.srt, upload_to_oss_flag=args.upload_oss)
        sys.exit(0 if success else 1)

    # Handle flash model (local file mode)
    else:
        if not args.path:
            print("Error: path is required for flash model")
            print("Example: uv run qwen_asr.py audio.mp3")
            sys.exit(1)

        input_path = Path(args.path)
        output_dir = Path(args.output) if args.output else None

        if not input_path.exists():
            print(f"Error: Path not found: {input_path}")
            sys.exit(1)

        if input_path.is_file():
            if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                print(f"Error: Unsupported file type: {input_path.suffix}")
                sys.exit(1)
            success = process_file(input_path, api_key, output_dir, args.context, args.threads, args.srt,
                                   args.segment_threshold, args.max_segment, args.min_silence)
            sys.exit(0 if success else 1)

        elif input_path.is_dir():
            files = find_media_files(input_path)
            if not files:
                print(f"No supported media files found in: {input_path}")
                sys.exit(1)

            print(f"Found {len(files)} media files")
            success_count = 0
            for file_path in files:
                if process_file(file_path, api_key, output_dir, args.context, args.threads, args.srt,
                               args.segment_threshold, args.max_segment, args.min_silence):
                    success_count += 1

            print(f"\nCompleted: {success_count}/{len(files)} files")
            sys.exit(0 if success_count > 0 else 1)


if __name__ == '__main__':
    main()

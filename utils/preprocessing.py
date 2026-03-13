import os
import subprocess
from typing import List

import cv2
import torch
import numpy as np
from PIL import Image

from utils.logger import logger


def extract_frames(video_path: str, target_fps: float = 1.0) -> List[Image.Image]:
    """Sample frames from a video at *target_fps* frames per second.
    Tries OpenCV first, then falls back to FFmpeg for better codec support.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # ── Try OpenCV ──────────────────────────────────────────────────
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError("OpenCV failed to open video")

        native_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if native_fps <= 0:
            raise RuntimeError("OpenCV reported non-positive FPS")

        frame_interval = max(1, int(round(native_fps / target_fps)))
        logger.info("Extracting frames (OpenCV): %s (fps=%.2f, total=%d, interval=%d)",
                    os.path.basename(video_path), native_fps, total_frames, frame_interval)

        frames: List[Image.Image] = []
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            if frame_idx % frame_interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(rgb))
            frame_idx += 1
        cap.release()

        if len(frames) > 0:
            logger.info("Extracted %d frames using OpenCV", len(frames))
            return frames
    except Exception as e:
        logger.warning("OpenCV frame extraction failed or returned 0 frames: %s", e)

    # ── Fallback to FFmpeg ───────────────────────────────────────────
    logger.info("Falling back to FFmpeg for frame extraction...")
    return extract_frames_ffmpeg(video_path, target_fps)


def extract_frames_ffmpeg(video_path: str, target_fps: float = 1.0) -> List[Image.Image]:
    """Extract frames using a raw FFmpeg subprocess for maximum compatibility."""
    import tempfile
    import shutil
    
    ffmpeg_exe = _find_ffmpeg()
    temp_dir = tempfile.mkdtemp(prefix="truthx_frames_")
    
    try:
        # Use ffmpeg to save frames as images to disk
        # -q:v 2 is high quality JPEG
        out_pattern = os.path.join(temp_dir, "frame_%04d.jpg")
        cmd = [
            ffmpeg_exe, "-y",
            "-i", video_path,
            "-vf", f"fps={target_fps}",
            "-q:v", "2",
            out_pattern
        ]
        
        logger.info("Running FFmpeg: %s", " ".join(cmd))
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Load images from disk
        files = sorted([f for f in os.listdir(temp_dir) if f.endswith(".jpg")])
        frames = []
        for f in files:
            img_path = os.path.join(temp_dir, f)
            with Image.open(img_path) as img:
                frames.append(img.convert("RGB"))
        
        logger.info("Extracted %d frames using FFmpeg fallback", len(frames))
        return frames
    except Exception as e:
        logger.error("FFmpeg frame extraction totally failed: %s", e)
        return []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def detect_and_crop_faces(frames: List[Image.Image]) -> List[Image.Image]:
    """Detect faces in frames using OpenCV Haar cascades and return cropped images.
    If no face is detected, returns the original frame.
    """
    if not frames:
        return []

    logger.info("Initializing OpenCV Haar Cascade for face detection")
    print(f"  Running Face Detection on {len(frames)} frames...", end="", flush=True)

    # Use OpenCV's built-in Haar cascade path
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    faces_found = 0
    cropped_images = []

    for frame in frames:
        # Convert PIL to OpenCV BGR
        open_cv_image = np.array(frame)
        if len(open_cv_image.shape) == 3 and open_cv_image.shape[2] == 3:
            # Note: frame is usually RGB
            open_cv_image = open_cv_image[:, :, ::-1].copy()

        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            # Optional: find largest face
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest_face

            # Crop face from original PIL image
            face_crop = frame.crop((x, y, x + w, y + h))
            cropped_images.append(face_crop)
            faces_found += 1
        else:
            cropped_images.append(frame)

    logger.info("Face detection complete: found faces in %d/%d frames", faces_found, len(frames))
    print(f" done ({faces_found} faces found).")
    
    return cropped_images


def _find_ffmpeg() -> str:
    """Find ffmpeg executable in local directory or system path."""
    # check local project bin
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_bin = os.path.join(project_root, "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.isfile(local_bin):
        return local_bin
    
    local_root_exe = os.path.join(project_root, "ffmpeg", "ffmpeg.exe")
    if os.path.isfile(local_root_exe):
        return local_root_exe

    # Fallback to system path
    return "ffmpeg"


def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio track from a video file to 16 kHz mono WAV using ffmpeg.

    Returns the path to the output WAV file.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.wav")

    ffmpeg_exe = _find_ffmpeg()
    
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ]

    logger.info("Extracting audio with %s: %s → %s", ffmpeg_exe, video_path, output_path)
    try:
        # Use shell=False to avoid Windows vs *nix issues, but on Windows check=True is enough usually
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            f"ffmpeg not found at '{ffmpeg_exe}'. Install ffmpeg and ensure it is on your PATH or in ffmpeg/bin"
        )

    except subprocess.CalledProcessError as exc:
        logger.error("ffmpeg failed (code %d): %s", exc.returncode, exc.stderr)
        raise RuntimeError(f"Audio extraction failed: {exc.stderr.strip()}")

    logger.info("Audio saved to %s", output_path)
    return output_path

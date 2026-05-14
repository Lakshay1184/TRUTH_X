"""truth.x — Preprocessing: Adaptive frame sampling, face detection, alignment, audio extraction."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.utils.logger import logger
from backend.utils.media import find_ffmpeg


# ─── Adaptive Frame Extraction ──────────────────────────────────────────

def extract_frames_adaptive(
    video_path: str,
    target_fps: float = 1.0,
    max_frames: int = 32,
    min_frames: int = 8,
    scene_change_threshold: float = 30.0,
) -> List[Image.Image]:
    """Extract frames using adaptive sampling with scene-change detection.

    Strategy:
        1. Extract at target_fps
        2. Detect scene changes (histogram difference)
        3. Always include keyframes around scene changes
        4. Cap at max_frames, ensure at least min_frames
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Try OpenCV first
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError("OpenCV failed to open video")

        native_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if native_fps <= 0:
            raise RuntimeError("Non-positive FPS")

        frame_interval = max(1, int(round(native_fps / target_fps)))
        logger.info("Adaptive extraction: %s (fps=%.2f, total=%d, interval=%d)",
                     os.path.basename(video_path), native_fps, total_frames, frame_interval)

        candidates: List[Tuple[int, Image.Image, float]] = []
        prev_hist = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
                hist = cv2.normalize(hist, hist).flatten()

                # Scene change score
                scene_score = 0.0
                if prev_hist is not None:
                    scene_score = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                prev_hist = hist

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                candidates.append((frame_idx, pil_img, scene_score))

            frame_idx += 1

        cap.release()

        if not candidates:
            logger.warning("No frames extracted via OpenCV, trying FFmpeg fallback")
            return _extract_frames_ffmpeg(video_path, target_fps)

        # ── Adaptive selection ──
        if len(candidates) <= max_frames:
            selected = candidates
        else:
            # Always include first and last
            selected = [candidates[0], candidates[-1]]

            # Add scene-change frames (top scorers)
            scene_sorted = sorted(candidates[1:-1], key=lambda x: x[2], reverse=True)
            scene_budget = min(max_frames // 3, len(scene_sorted))
            scene_indices = set()
            for c in scene_sorted[:scene_budget]:
                selected.append(c)
                scene_indices.add(c[0])

            # Fill remaining with uniform sampling
            remaining = [c for c in candidates if c[0] not in scene_indices and c not in selected]
            remaining_budget = max_frames - len(selected)
            if remaining and remaining_budget > 0:
                step = max(1, len(remaining) // remaining_budget)
                for i in range(0, len(remaining), step):
                    if len(selected) >= max_frames:
                        break
                    selected.append(remaining[i])

            # Sort by frame index
            selected.sort(key=lambda x: x[0])

        frames = [img for _, img, _ in selected]
        logger.info("Adaptive extraction: selected %d/%d frames (scene changes detected: %d)",
                     len(frames), len(candidates),
                     sum(1 for _, _, s in candidates if s > scene_change_threshold))
        return frames

    except Exception as e:
        logger.warning("OpenCV extraction failed: %s, falling back to FFmpeg", e)
        return _extract_frames_ffmpeg(video_path, target_fps)


def _extract_frames_ffmpeg(video_path: str, target_fps: float = 1.0) -> List[Image.Image]:
    """Extract frames using FFmpeg subprocess (maximum codec compatibility)."""
    ffmpeg_exe = find_ffmpeg()
    temp_dir = tempfile.mkdtemp(prefix="truthx_frames_")
    try:
        out_pattern = os.path.join(temp_dir, "frame_%04d.jpg")
        cmd = [ffmpeg_exe, "-y", "-i", video_path, "-vf", f"fps={target_fps}", "-q:v", "2", out_pattern]
        logger.info("FFmpeg frame extraction: %s", " ".join(cmd))
        subprocess.run(cmd, capture_output=True, check=True)

        files = sorted(f for f in os.listdir(temp_dir) if f.endswith(".jpg"))
        frames = []
        for f in files:
            with Image.open(os.path.join(temp_dir, f)) as img:
                frames.append(img.convert("RGB").copy())

        logger.info("FFmpeg extracted %d frames", len(frames))
        return frames
    except Exception as e:
        logger.error("FFmpeg frame extraction failed: %s", e)
        return []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ─── Face Detection & Quality Filtering ──────────────────────────────────

def detect_and_crop_faces(
    frames: List[Image.Image],
    quality_threshold: float = 100.0,
) -> List[Image.Image]:
    """Detect faces using Haar cascades, crop, and filter by quality.

    Quality is measured by Laplacian variance (higher = sharper).
    Frames with no face or very blurry faces return the original frame.
    """
    if not frames:
        return []

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    faces_found = 0
    quality_rejected = 0
    cropped_images = []

    for frame in frames:
        arr = np.array(frame)
        if len(arr.shape) == 3 and arr.shape[2] == 3:
            bgr = arr[:, :, ::-1].copy()
        else:
            bgr = arr

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            # Pick largest face
            largest = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest

            # Quality check (Laplacian variance — measures sharpness)
            face_region = gray[y:y + h, x:x + w]
            laplacian_var = cv2.Laplacian(face_region, cv2.CV_64F).var()

            if laplacian_var >= quality_threshold:
                # Add margin around face (20%)
                margin = int(max(w, h) * 0.2)
                x1 = max(0, x - margin)
                y1 = max(0, y - margin)
                x2 = min(arr.shape[1], x + w + margin)
                y2 = min(arr.shape[0], y + h + margin)
                face_crop = frame.crop((x1, y1, x2, y2))
                cropped_images.append(face_crop)
                faces_found += 1
            else:
                quality_rejected += 1
                cropped_images.append(frame)
        else:
            cropped_images.append(frame)

    logger.info("Face detection: %d/%d faces found (%d rejected for quality)",
                faces_found, len(frames), quality_rejected)
    return cropped_images


# ─── Face Alignment (lightweight) ────────────────────────────────────────

def align_faces(frames: List[Image.Image]) -> List[Image.Image]:
    """Apply basic face alignment using eye detection.

    Uses Haar cascade for eyes within detected face region,
    then applies affine rotation to align eyes horizontally.
    """
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    aligned = []

    for frame in frames:
        arr = np.array(frame)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(50, 50))

        if len(faces) == 0:
            aligned.append(frame)
            continue

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        roi_gray = gray[y:y + h, x:x + w]
        eyes = eye_cascade.detectMultiScale(roi_gray, 1.1, 5, minSize=(15, 15))

        if len(eyes) >= 2:
            # Sort by x-coordinate to get left and right eye
            eyes_sorted = sorted(eyes, key=lambda e: e[0])
            left_eye = (x + eyes_sorted[0][0] + eyes_sorted[0][2] // 2,
                        y + eyes_sorted[0][1] + eyes_sorted[0][3] // 2)
            right_eye = (x + eyes_sorted[1][0] + eyes_sorted[1][2] // 2,
                         y + eyes_sorted[1][1] + eyes_sorted[1][3] // 2)

            # Compute rotation angle
            dy = right_eye[1] - left_eye[1]
            dx = right_eye[0] - left_eye[0]
            angle = np.degrees(np.arctan2(dy, dx))

            if abs(angle) > 0.5:  # Only rotate if meaningful
                center = ((left_eye[0] + right_eye[0]) // 2, (left_eye[1] + right_eye[1]) // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(arr, M, (arr.shape[1], arr.shape[0]))
                aligned.append(Image.fromarray(rotated))
                continue

        aligned.append(frame)

    return aligned


# ─── Preprocessing Enhancements ──────────────────────────────────────────

def enhance_artifacts(frame: Image.Image) -> Image.Image:
    """Apply unsharp masking to amplify potential GAN fingerprints."""
    arr = np.array(frame)
    blurred = cv2.GaussianBlur(arr, (0, 0), 3)
    sharpened = cv2.addWeighted(arr, 1.5, blurred, -0.5, 0)
    return Image.fromarray(np.clip(sharpened, 0, 255).astype(np.uint8))


def normalize_frame(frame: Image.Image, target_size: Tuple[int, int] = (224, 224)) -> Image.Image:
    """Resize and normalize a frame for model input."""
    return frame.resize(target_size, Image.LANCZOS)


# ─── Audio Extraction ────────────────────────────────────────────────────

def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio track from video to 16 kHz mono WAV."""
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(output_dir, f"{base}.wav")
    ffmpeg_exe = find_ffmpeg()

    cmd = [ffmpeg_exe, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output_path]
    logger.info("Extracting audio: %s → %s", video_path, output_path)

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"ffmpeg not found at '{ffmpeg_exe}'")
    except subprocess.CalledProcessError as exc:
        logger.error("ffmpeg failed (code %d): %s", exc.returncode, exc.stderr)
        raise RuntimeError(f"Audio extraction failed: {exc.stderr.strip()}")

    logger.info("Audio saved to %s", output_path)
    return output_path

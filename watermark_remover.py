#!/usr/bin/env python3
"""CPU-only Seedance watermark remover."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

import cv2
import numpy as np

WATERMARK_SEEDANCE = "seedance"
WATERMARK_GEMINI = "gemini"
WATERMARK_TYPES = (WATERMARK_SEEDANCE, WATERMARK_GEMINI)


def _sparkle_template(size=64):
    """Return a filled four-point sparkle template used to reject non-logo bright blobs."""
    edge = size - 1
    points = np.array(
        [
            (0.50 * edge, 0.00 * edge),
            (0.62 * edge, 0.36 * edge),
            (1.00 * edge, 0.50 * edge),
            (0.62 * edge, 0.64 * edge),
            (0.50 * edge, 1.00 * edge),
            (0.38 * edge, 0.64 * edge),
            (0.00 * edge, 0.50 * edge),
            (0.38 * edge, 0.36 * edge),
        ],
        dtype=np.int32,
    )
    template = np.zeros((size, size), dtype=np.uint8)
    cv2.fillPoly(template, [points], 255)
    return template


SPARKLE_TEMPLATE = _sparkle_template()


def _sparkle_shape_score(component_mask):
    resized = cv2.resize(component_mask, SPARKLE_TEMPLATE.shape[::-1], interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(resized, 80, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    intersection = np.logical_and(binary > 0, SPARKLE_TEMPLATE > 0).sum()
    union = np.logical_or(binary > 0, SPARKLE_TEMPLATE > 0).sum()
    return float(intersection / max(1, union))


def _find_ffmpeg_executable():
    candidates = []
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
        candidates.extend(
            [
                os.path.join(app_dir, "ffmpeg.exe"),
                os.path.join(app_dir, "_internal", "ffmpeg.exe"),
            ]
        )
    bundle_dir = getattr(sys, "_MEIPASS", "")
    if bundle_dir:
        candidates.extend(
            [
                os.path.join(bundle_dir, "ffmpeg.exe"),
                os.path.join(bundle_dir, "_internal", "ffmpeg.exe"),
            ]
        )
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.extend(
        [
            os.path.join(script_dir, "ffmpeg.exe"),
            os.path.join(script_dir, "_internal", "ffmpeg.exe"),
        ]
    )
    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        candidates.append(path_ffmpeg)

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return "ffmpeg"


def _print_ffmpeg_failure(completed):
    print("Error: ffmpeg reassembly failed.")
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    if stderr:
        print("ffmpeg stderr:")
        print(stderr[-4000:])
    if stdout:
        print("ffmpeg stdout:")
        print(stdout[-4000:])


def build_default_output_path(input_path):
    base, _ext = os.path.splitext(input_path)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_clean_{stamp}_{uuid.uuid4().hex[:6]}.mp4"


def _normalize_watermark_types(watermark_types=None):
    if watermark_types is None:
        return (WATERMARK_SEEDANCE,)
    if isinstance(watermark_types, str):
        watermark_types = (watermark_types,)
    normalized = tuple(dict.fromkeys(str(item).lower() for item in watermark_types))
    invalid = [item for item in normalized if item not in WATERMARK_TYPES]
    if invalid:
        raise ValueError(f"Unsupported watermark type: {', '.join(invalid)}")
    return normalized or (WATERMARK_SEEDANCE,)


def _auto_detect(frames, mean_frame, width, height, watermark_types=None):
    detected = _auto_detect_with_type(frames, mean_frame, width, height, watermark_types)
    return detected[0] if detected else None


def _auto_detect_with_type(frames, mean_frame, width, height, watermark_types=None):
    for watermark_type in _normalize_watermark_types(watermark_types):
        if watermark_type == WATERMARK_GEMINI:
            region = _auto_detect_gemini(frames, mean_frame, width, height)
        else:
            region = _auto_detect_seedance(frames, mean_frame, width, height)
        if region is not None:
            return region, watermark_type
    return None


def _auto_detect_seedance(frames, mean_frame, width, height):
    """
    Scan the four corners for a static watermark.

    Scoring: edge_density × temporal_stability.
    Static text has crisp edges and low frame-to-frame variation; moving content
    scores lower and is ignored.
    """
    stack = np.stack(frames, axis=0)
    std_map = np.std(stack, axis=0).mean(axis=2)

    shorter_side = min(width, height)
    longer_side = max(width, height)
    is_portrait = height > width

    base_h = max(60, int(height * 0.08), int(shorter_side * 0.10))
    base_w = max(120, int(width * 0.12), int(shorter_side * 0.16))
    if is_portrait:
        base_w = max(base_w, int(longer_side * 0.18))

    corner_sizes = [
        (base_h, base_w),
        (max(base_h, int(height * 0.12)), max(base_w, int(width * 0.20))),
    ]
    candidates = []
    for corner_h, corner_w in corner_sizes:
        corner_h = min(height, corner_h)
        corner_w = min(width, corner_w)
        candidates.extend(
            [
                (0, 0, corner_h, corner_w),
                (0, width - corner_w, corner_h, width),
                (height - corner_h, 0, height, corner_w),
                (height - corner_h, width - corner_w, height, width),
            ]
        )

    small_sizes = [
        (max(42, int(shorter_side * 0.08)), max(64, int(shorter_side * 0.12))),
        (max(60, int(shorter_side * 0.11)), max(90, int(shorter_side * 0.17))),
        (max(80, int(shorter_side * 0.14)), max(120, int(shorter_side * 0.22))),
    ]
    offsets = sorted({0, 12, 24, max(32, int(shorter_side * 0.05)), max(48, int(shorter_side * 0.08))})
    for window_h, window_w in small_sizes:
        window_h = min(height, window_h)
        window_w = min(width, window_w)
        for offset_y in offsets:
            for offset_x in offsets:
                if offset_x + window_w > width or offset_y + window_h > height:
                    continue
                candidates.extend(
                    [
                        (offset_y, offset_x, offset_y + window_h, offset_x + window_w),
                        (offset_y, width - offset_x - window_w, offset_y + window_h, width - offset_x),
                        (height - offset_y - window_h, offset_x, height - offset_y, offset_x + window_w),
                        (
                            height - offset_y - window_h,
                            width - offset_x - window_w,
                            height - offset_y,
                            width - offset_x,
                        ),
                    ]
                )

    best, best_score = None, 0
    seen = set()
    for r1, c1, r2, c2 in candidates:
        candidate = (r1, c1, r2, c2)
        if candidate in seen:
            continue
        seen.add(candidate)
        roi_gray = cv2.cvtColor(mean_frame[r1:r2, c1:c2], cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(roi_gray, 20, 60)
        edge_density = edges.mean() / 255.0
        temporal_std = std_map[r1:r2, c1:c2].mean()
        stability = 1.0 / (1.0 + temporal_std)

        if edge_density > 0.002:
            ys, xs = np.where(edges > 0)
            if len(xs) > 20:
                bbox_w = int(xs.max() - xs.min()) + 1
                bbox_h = int(ys.max() - ys.min()) + 1
                bbox_area = bbox_w * bbox_h
                roi_area = max(1, (r2 - r1) * (c2 - c1))
                compactness = max(0.15, 1.0 - min(1.0, bbox_area / roi_area))
                score = edge_density * stability * compactness
                if score <= best_score:
                    continue

                best_score = score
                pad = 8
                x = max(0, c1 + int(xs.min()) - pad)
                y = max(0, r1 + int(ys.min()) - pad)
                w = min(width - x, bbox_w + 2 * pad)
                h = min(height - y, bbox_h + 2 * pad)
                best = (x, y, w, h)

    return best


def _auto_detect_gemini(frames, mean_frame, width, height):
    """Find a small bright sparkle-style logo near the lower-right video area."""
    stack = np.stack(frames, axis=0)
    std_map = np.std(stack, axis=0).mean(axis=2)
    shorter_side = min(width, height)
    search_left = int(width * 0.50)
    search_top = int(height * 0.50)
    roi = mean_frame[search_top:height, search_left:width]
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(9, shorter_side * 0.018))
    bright_delta = cv2.subtract(gray, background)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    raw = np.where(
        ((value >= 115) & (saturation <= 145) & (bright_delta >= 1)) | ((value >= 185) & (saturation <= 110)),
        255,
        0,
    )
    raw = raw.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    raw = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, kernel, iterations=1)
    raw = cv2.morphologyEx(raw, cv2.MORPH_OPEN, kernel, iterations=1)

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(raw)
    min_box = max(18, int(shorter_side * 0.025))
    min_area = max(45, int(shorter_side * shorter_side * 0.00008))
    max_area = max(5000, int(shorter_side * shorter_side * 0.018))
    max_box = max(90, int(shorter_side * 0.13))
    target_box = max(34.0, shorter_side * 0.058)
    target_area = target_box * target_box
    best_region, best_score = None, 0.0

    for component_id in range(1, count):
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        x = int(stats[component_id, cv2.CC_STAT_LEFT])
        y = int(stats[component_id, cv2.CC_STAT_TOP])
        w = int(stats[component_id, cv2.CC_STAT_WIDTH])
        h = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        if area < min_area or area > max_area or w < min_box or h < min_box or w > max_box or h > max_box:
            continue
        aspect = w / max(1, h)
        if not 0.45 <= aspect <= 1.75:
            continue
        fill_ratio = area / max(1, w * h)
        if not 0.12 <= fill_ratio <= 0.75:
            continue

        component_mask = np.where(labels[y : y + h, x : x + w] == component_id, 255, 0).astype(np.uint8)
        shape_score = _sparkle_shape_score(component_mask)
        if shape_score < 0.50:
            continue

        center_x, center_y = centroids[component_id]
        abs_x = search_left + x
        abs_y = search_top + y
        abs_cx = search_left + float(center_x)
        abs_cy = search_top + float(center_y)
        if abs_cx < width * 0.55 or abs_cy < height * 0.55:
            continue
        component_std = float(std_map[abs_y : abs_y + h, abs_x : abs_x + w].mean())
        stability = 1.0 / (1.0 + component_std)
        corner_bias = (abs_cx / width) ** 1.4 * (abs_cy / height) ** 1.6
        compactness = 1.0 - min(1.0, abs(1.0 - aspect) * 0.45)
        size_score = target_box / (target_box + abs(w - target_box) + abs(h - target_box))
        area_score = target_area / (target_area + abs(area - target_area))
        score = (
            stability
            * corner_bias
            * compactness
            * size_score
            * (0.45 + area_score)
            * (0.2 + fill_ratio)
            * (shape_score**4)
        )
        if score <= best_score:
            continue

        pad = max(18, int(shorter_side * 0.025))
        region_x = max(0, abs_x - pad)
        region_y = max(0, abs_y - pad)
        region_w = min(width - region_x, w + 2 * pad)
        region_h = min(height - region_y, h + 2 * pad)
        best_score = score
        best_region = (region_x, region_y, region_w, region_h)

    return best_region


def _build_mask(mean_frame_bgr, region_xywh, frame_shape, watermark_type=WATERMARK_SEEDANCE):
    if watermark_type == WATERMARK_GEMINI:
        return _build_gemini_mask(mean_frame_bgr, region_xywh, frame_shape)
    return _build_seedance_mask(mean_frame_bgr, region_xywh, frame_shape)


def _build_seedance_mask(mean_frame_bgr, region_xywh, frame_shape):
    """Build a sparse text mask using Canny edges from the mean frame."""
    x, y, w, h = region_xywh
    frame_height, frame_width = frame_shape[:2]
    roi_gray = cv2.cvtColor(mean_frame_bgr[y : y + h, x : x + w], cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(roi_gray, 30, 80)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=1)
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(dilated)
    clean = np.zeros_like(dilated)
    for component_id in range(1, component_count):
        if stats[component_id, cv2.CC_STAT_AREA] >= 100:
            clean[labels == component_id] = 255
    if clean.sum() == 0:
        clean = np.full((h, w), 255, dtype=np.uint8)
    mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
    mask[y : y + h, x : x + w] = clean
    return mask


def _build_gemini_mask(mean_frame_bgr, region_xywh, frame_shape):
    """Build a filled mask for bright translucent sparkle logos."""
    x, y, w, h = region_xywh
    frame_height, frame_width = frame_shape[:2]
    roi = mean_frame_bgr[y : y + h, x : x + w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(7, min(w, h) * 0.10))
    bright_delta = cv2.subtract(gray, background)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    mask_roi = np.where(
        ((value >= 120) & (saturation <= 140) & (bright_delta >= 2)) | ((value >= 190) & (saturation <= 100)),
        255,
        0,
    ).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_OPEN, kernel, iterations=1)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask_roi)
    clean = np.zeros_like(mask_roi)
    min_area = max(45, int(min(w, h) * min(w, h) * 0.01))
    for component_id in range(1, component_count):
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        comp_w = int(stats[component_id, cv2.CC_STAT_WIDTH])
        comp_h = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        if area >= min_area and comp_w >= 8 and comp_h >= 8:
            clean[labels == component_id] = 255
    if clean.sum() == 0:
        clean = mask_roi
    clean = cv2.dilate(clean, kernel, iterations=2)

    mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
    mask[y : y + h, x : x + w] = clean
    return mask


def _inpaint_telea(frame_bgr, mask):
    """Fast OpenCV TELEA inpainting."""
    return cv2.inpaint(frame_bgr, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)


def remove_watermark(input_path, output_path, manual_region=None, watermark_types=None):
    cap = cv2.VideoCapture(input_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {width}x{height} @ {fps:.2f} fps | {total} frames")

    print("Sampling frames for watermark detection...")
    sample_frames = []
    step = max(1, total // 60)
    for frame_index in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = cap.read()
        if ret:
            sample_frames.append(frame.astype(np.float32))
        if len(sample_frames) >= 60:
            break

    if not sample_frames:
        print("Error: could not read any frames.")
        cap.release()
        return False

    mean_frame = np.mean(np.stack(sample_frames), axis=0).astype(np.uint8)

    selected_types = _normalize_watermark_types(watermark_types)
    if manual_region:
        x, y, w, h = manual_region
        watermark_type = selected_types[0]
        print(f"Using manual region: x={x} y={y} w={w} h={h}")
    else:
        detected = _auto_detect_with_type(sample_frames, mean_frame, width, height, selected_types)
        if detected is None:
            print("Error: auto-detection failed. Try -r x,y,w,h to specify the region manually.")
            cap.release()
            return False
        region, watermark_type = detected
        x, y, w, h = region
        print(f"Detected {watermark_type} watermark region: x={x} y={y} w={w} h={h}")

    mask = _build_mask(mean_frame, (x, y, w, h), (height, width), watermark_type)
    print(f"Mask: {int(mask.sum() // 255)} pixels")

    frames_dir = tempfile.mkdtemp(prefix="seedance_wm_")
    print(f"Inpainting {total} frames with OpenCV TELEA...")

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        for frame_index in range(total):
            ret, frame = cap.read()
            if not ret:
                break
            result = _inpaint_telea(frame, mask)
            cv2.imwrite(os.path.join(frames_dir, f"{frame_index:06d}.png"), result)
            if (frame_index + 1) % 30 == 0 or frame_index == total - 1:
                print(f"  {frame_index + 1}/{total}", end="\r", flush=True)
        cap.release()
        print()

        print("Reassembling video with original audio...")
        ffmpeg_executable = _find_ffmpeg_executable()
        print(f"Using ffmpeg: {ffmpeg_executable}")
        cmd = [
            ffmpeg_executable,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            os.path.join(frames_dir, "%06d.png"),
            "-i",
            input_path,
            "-map",
            "0:v",
            "-map",
            "1:a?",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)

    if completed.returncode == 0:
        in_mb = os.path.getsize(input_path) / 1024 / 1024
        out_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"\nDone.  {in_mb:.1f} MB  ->  {out_mb:.1f} MB")
        print(f"Output: {output_path}")
        return True

    _print_ffmpeg_failure(completed)
    return False


def parse_region(value):
    try:
        region = tuple(int(part) for part in value.split(","))
    except ValueError:
        return None
    if len(region) != 4:
        return None
    return region


def main():
    parser = argparse.ArgumentParser(description="Remove small static corner watermarks from videos.")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("-o", "--output", help="Output path (default: <input>_clean_<timestamp>_<id>.mp4)")
    parser.add_argument(
        "-r",
        "--region",
        help="Manual watermark region as x,y,w,h — skips auto-detection",
    )
    parser.add_argument(
        "--type",
        action="append",
        choices=WATERMARK_TYPES,
        help="Watermark type to remove. Can be repeated. Default: seedance",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    output = args.output or build_default_output_path(args.input)

    region = None
    if args.region:
        region = parse_region(args.region)
        if region is None:
            print("Error: --region must be four comma-separated integers: x,y,w,h")
            sys.exit(1)

    ok = remove_watermark(args.input, output, manual_region=region, watermark_types=args.type)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""CPU-only Seedance watermark remover."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np


def _auto_detect(frames, mean_frame, width, height):
    """
    Scan the four corners for a static watermark.

    Scoring: edge_density × temporal_stability.
    Static text has crisp edges and low frame-to-frame variation; moving content
    scores lower and is ignored.
    """
    stack = np.stack(frames, axis=0)
    std_map = np.std(stack, axis=0).mean(axis=2)

    corner_h = max(60, int(height * 0.08))
    corner_w = max(120, int(width * 0.12))
    corners = [
        (0, 0, corner_h, corner_w),
        (0, width - corner_w, corner_h, width),
        (height - corner_h, 0, height, corner_w),
        (height - corner_h, width - corner_w, height, width),
    ]

    best, best_score = None, 0
    for r1, c1, r2, c2 in corners:
        roi_gray = cv2.cvtColor(mean_frame[r1:r2, c1:c2], cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(roi_gray, 20, 60)
        edge_density = edges.mean() / 255.0
        temporal_std = std_map[r1:r2, c1:c2].mean()
        stability = 1.0 / (1.0 + temporal_std)
        score = edge_density * stability

        if score > best_score and edge_density > 0.002:
            ys, xs = np.where(edges > 0)
            if len(xs) > 20:
                best_score = score
                pad = 8
                x = max(0, c1 + int(xs.min()) - pad)
                y = max(0, r1 + int(ys.min()) - pad)
                w = min(width - x, int(xs.max() - xs.min()) + 1 + 2 * pad)
                h = min(height - y, int(ys.max() - ys.min()) + 1 + 2 * pad)
                best = (x, y, w, h)

    return best


def _build_mask(mean_frame_bgr, region_xywh, frame_shape):
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


def _inpaint_telea(frame_bgr, mask):
    """Fast OpenCV TELEA inpainting."""
    return cv2.inpaint(frame_bgr, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)


def remove_watermark(input_path, output_path, manual_region=None):
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

    if manual_region:
        x, y, w, h = manual_region
        print(f"Using manual region: x={x} y={y} w={w} h={h}")
    else:
        region = _auto_detect(sample_frames, mean_frame, width, height)
        if region is None:
            print("Error: auto-detection failed. Try -r x,y,w,h to specify the region manually.")
            cap.release()
            return False
        x, y, w, h = region
        print(f"Detected watermark region: x={x} y={y} w={w} h={h}")

    mask = _build_mask(mean_frame, (x, y, w, h), (height, width))
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
        cmd = [
            "ffmpeg",
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
            "-y",
        ]
        ret_code = subprocess.run(cmd, capture_output=True).returncode

    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)

    if ret_code == 0:
        in_mb = os.path.getsize(input_path) / 1024 / 1024
        out_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"\nDone.  {in_mb:.1f} MB  →  {out_mb:.1f} MB")
        print(f"Output: {output_path}")
        return True

    print("Error: ffmpeg reassembly failed.")
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
    parser = argparse.ArgumentParser(description="Remove Seedance 2.0 'AI生成' watermark from videos.")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("-o", "--output", help="Output path (default: <input>_clean.mp4)")
    parser.add_argument(
        "-r",
        "--region",
        help="Manual watermark region as x,y,w,h — skips auto-detection",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    output = args.output or os.path.splitext(args.input)[0] + "_clean.mp4"

    region = None
    if args.region:
        region = parse_region(args.region)
        if region is None:
            print("Error: --region must be four comma-separated integers: x,y,w,h")
            sys.exit(1)

    ok = remove_watermark(args.input, output, manual_region=region)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

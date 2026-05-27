from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from seedance_gui import (
    SeedanceApp,
    build_centered_geometry,
    build_output_path,
    choose_window_size,
    get_ui_text,
    normalize_path,
    parse_region,
)
from watermark_remover import WATERMARK_GEMINI, _auto_detect


def absolute_widget_bottom(widget, root) -> int:
    y = 0
    current = widget
    while current is not root:
        y += current.winfo_y()
        current = current.master
    return y + widget.winfo_height()


class SeedanceGuiPureLogicTests(unittest.TestCase):
    def test_parse_region_accepts_four_non_negative_integers_with_positive_size(self) -> None:
        self.assertEqual(parse_region("1, 2, 30, 40"), (1, 2, 30, 40))

    def test_parse_region_rejects_invalid_values(self) -> None:
        invalid_values = ["", "1,2,3", "1,2,0,4", "1,2,-3,4", "x,y,w,h"]
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertIsNone(parse_region(value))

    def test_normalize_path_handles_quoted_and_file_url_values(self) -> None:
        self.assertEqual(normalize_path('"C:/tmp/video.mp4"'), Path("C:/tmp/video.mp4"))
        self.assertEqual(normalize_path("{file:///C:/tmp/video.mp4}"), Path("C:/tmp/video.mp4"))

    def test_choose_window_size_uses_vertical_desktop_window_without_fullscreen(self) -> None:
        width, height, min_width, min_height = choose_window_size(1920, 1080)
        self.assertEqual((width, height), (900, 900))
        self.assertEqual((min_width, min_height), (760, 760))

    def test_build_centered_geometry_clamps_to_small_screen(self) -> None:
        self.assertEqual(build_centered_geometry(1024, 768), "900x720+62+24")

    def test_initial_layout_shows_primary_action_without_resize(self) -> None:
        app = SeedanceApp(hidden=False)
        try:
            root = app.root
            root.update_idletasks()
            root.update()
            button_bottom = absolute_widget_bottom(app.run_btn, root)
            self.assertLessEqual(button_bottom, root.winfo_height())
        finally:
            app.destroy()

    def test_ui_text_supports_english_russian_and_chinese(self) -> None:
        self.assertEqual(get_ui_text("English", "browse"), "Browse video")
        self.assertEqual(get_ui_text("Русский", "browse"), "Выбрать видео")
        self.assertEqual(get_ui_text("中文", "browse"), "选择视频")

    def test_build_output_path_avoids_overwriting_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "clip.mp4"
            first = folder / "clip_clean.mp4"
            source.write_bytes(b"source")
            first.write_bytes(b"existing")

            self.assertEqual(build_output_path(source, folder), folder / "clip_clean_2.mp4")

    def test_auto_detect_covers_wide_top_right_watermark_on_portrait_video(self) -> None:
        width, height = 540, 960
        watermark_x, watermark_y = 350, 42
        frames = []
        for _ in range(8):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.putText(
                frame,
                "AI Generated",
                (watermark_x, watermark_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            frames.append(frame.astype(np.float32))

        mean_frame = np.mean(np.stack(frames), axis=0).astype(np.uint8)
        detected = _auto_detect(frames, mean_frame, width, height)

        self.assertIsNotNone(detected)
        x, y, w, h = detected
        self.assertGreaterEqual(x, width - 140)
        self.assertLessEqual(y, watermark_y)
        self.assertGreaterEqual(w, 60)
        self.assertGreaterEqual(h, 20)

    def test_auto_detect_prefers_compact_top_left_badge_over_bottom_scene_edges(self) -> None:
        width, height = 720, 1280
        frames = []
        for _ in range(8):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.rectangle(frame, (32, 18), (64, 42), (80, 80, 80), 1)
            cv2.putText(
                frame,
                "AI",
                (38, 37),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )
            for offset in range(0, 170, 12):
                cv2.line(frame, (0, height - 1 - offset), (220, height - 110 + offset // 2), (210, 210, 210), 2)
            frames.append(frame.astype(np.float32))

        mean_frame = np.mean(np.stack(frames), axis=0).astype(np.uint8)
        detected = _auto_detect(frames, mean_frame, width, height)

        self.assertIsNotNone(detected)
        x, y, w, h = detected
        self.assertLessEqual(x, 36)
        self.assertLessEqual(y, 20)
        self.assertGreaterEqual(w, 30)
        self.assertGreaterEqual(h, 20)

    def test_gemini_auto_detect_finds_bottom_right_sparkle_on_portrait_video(self) -> None:
        width, height = 540, 960
        frames = []
        for _ in range(8):
            frame = np.full((height, width, 3), (90, 112, 126), dtype=np.uint8)
            cv2.rectangle(frame, (480, 600), (535, 760), (230, 230, 230), -1)
            center = (430, 850)
            cv2.drawMarker(
                frame,
                center,
                (242, 242, 242),
                markerType=cv2.MARKER_STAR,
                markerSize=52,
                thickness=5,
                line_type=cv2.LINE_AA,
            )
            frames.append(frame.astype(np.float32))

        mean_frame = np.mean(np.stack(frames), axis=0).astype(np.uint8)
        detected = _auto_detect(frames, mean_frame, width, height, (WATERMARK_GEMINI,))

        self.assertIsNotNone(detected)
        x, y, w, h = detected
        self.assertLessEqual(x, center[0])
        self.assertLessEqual(y, center[1])
        self.assertGreaterEqual(x + w, center[0])
        self.assertGreaterEqual(y + h, center[1])


if __name__ == "__main__":
    unittest.main()

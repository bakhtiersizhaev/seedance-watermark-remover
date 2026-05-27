from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from build_exe import find_ffmpeg
from seedance_gui import (
    SeedanceApp,
    build_centered_geometry,
    build_output_path,
    choose_window_size,
    extract_zip_safely,
    get_ui_text,
    is_newer_version,
    normalize_path,
    parse_region,
    parse_version,
    prepare_self_update,
)
from watermark_remover import WATERMARK_GEMINI, _auto_detect, build_default_output_path


def absolute_widget_right(widget, root) -> int:
    x = 0
    current = widget
    while current is not root:
        x += current.winfo_x()
        current = current.master
    return x + widget.winfo_width()


def absolute_widget_bottom(widget, root) -> int:
    y = 0
    current = widget
    while current is not root:
        y += current.winfo_y()
        current = current.master
    return y + widget.winfo_height()


def draw_gemini_sparkle(frame, center, size, color) -> None:
    cx, cy = center
    half = size / 2
    points = np.array(
        [
            (cx, cy - half),
            (cx + half * 0.24, cy - half * 0.14),
            (cx + half, cy),
            (cx + half * 0.24, cy + half * 0.14),
            (cx, cy + half),
            (cx - half * 0.24, cy + half * 0.14),
            (cx - half, cy),
            (cx - half * 0.24, cy - half * 0.14),
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(frame, [points], color, lineType=cv2.LINE_AA)


class SeedanceGuiPureLogicTests(unittest.TestCase):
    def test_parse_region_accepts_four_non_negative_integers_with_positive_size(self) -> None:
        self.assertEqual(parse_region("1, 2, 30, 40"), (1, 2, 30, 40))

    def test_parse_region_rejects_invalid_values(self) -> None:
        invalid_values = ["", "1,2,3", "1,2,0,4", "1,2,-3,4", "x,y,w,h"]
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertIsNone(parse_region(value))

    def test_parse_version_accepts_semver_tags(self) -> None:
        self.assertEqual(parse_version("v1.2.0"), (1, 2, 0))
        self.assertEqual(parse_version("1.2.5"), (1, 2, 5))
        self.assertEqual(parse_version("v2.0.0-beta"), (2, 0, 0))
        self.assertIsNone(parse_version("latest"))

    def test_is_newer_version_compares_semver_numbers(self) -> None:
        self.assertTrue(is_newer_version("v1.2.0", "1.1.9"))
        self.assertFalse(is_newer_version("v1.1.9", "1.2.0"))
        self.assertFalse(is_newer_version("v1.2.0", "1.2.0"))

    def test_prepare_self_update_rejects_source_runtime(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "portable EXE"):
            prepare_self_update({"version": "v9.9.9", "download_url": "https://example.invalid/app.zip"})

    def test_extract_zip_safely_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            zip_path = folder / "bad.zip"
            target = folder / "target"
            target.mkdir()
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("../escape.txt", "bad")

            with self.assertRaisesRegex(RuntimeError, "Unsafe path"):
                extract_zip_safely(zip_path, target)

    def test_normalize_path_handles_quoted_and_file_url_values(self) -> None:
        self.assertEqual(normalize_path('"C:/tmp/video.mp4"'), Path("C:/tmp/video.mp4"))
        self.assertEqual(normalize_path("{file:///C:/tmp/video.mp4}"), Path("C:/tmp/video.mp4"))

    def test_choose_window_size_uses_vertical_desktop_window_without_fullscreen(self) -> None:
        width, height, min_width, min_height = choose_window_size(1920, 1440)
        self.assertEqual((width, height), (900, 1200))
        self.assertEqual((min_width, min_height), (760, 760))

    def test_choose_window_size_clamps_to_shorter_desktop(self) -> None:
        width, height, min_width, min_height = choose_window_size(1920, 1080)
        self.assertEqual((width, height), (900, 1032))
        self.assertEqual((min_width, min_height), (760, 760))

    def test_build_centered_geometry_clamps_to_small_screen(self) -> None:
        self.assertEqual(build_centered_geometry(1024, 768), "900x720+62+24")

    def test_initial_layout_fits_key_controls_on_standard_desktop(self) -> None:
        app = SeedanceApp(hidden=False, check_updates_on_startup=False)
        try:
            root = app.root
            root.update_idletasks()
            root.update()
            button_bottom = absolute_widget_bottom(app.run_btn, root)
            self.assertLessEqual(button_bottom, root.winfo_height())

            root.geometry("900x1032+0+0")
            root.update_idletasks()
            root.update()
            footer_bottom = absolute_widget_bottom(app.telegram_contact_link, root)
            self.assertLessEqual(footer_bottom, root.winfo_height())
            self.assertIn("update", app.update_btn.cget("text").lower())
            update_bottom = absolute_widget_bottom(app.update_btn, root)
            self.assertLessEqual(update_bottom, root.winfo_height())
            self.assertLess(
                absolute_widget_right(app.telegram_contact_link, root),
                app.update_btn.winfo_rootx() - root.winfo_rootx(),
            )
            self.assertLessEqual(absolute_widget_right(app.update_btn, root), root.winfo_width())
            self.assertLessEqual(app.subtitle_label.cget("wraplength"), app.title_label.master.winfo_width())
        finally:
            app.destroy()

    def test_ui_text_supports_english_russian_and_chinese(self) -> None:
        self.assertEqual(get_ui_text("English", "browse"), "Browse video")
        self.assertEqual(get_ui_text("Русский", "browse"), "Выбрать видео")
        self.assertEqual(get_ui_text("中文", "browse"), "选择视频")

    def test_build_output_path_uses_unique_clean_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "clip.mp4"
            source.write_bytes(b"source")

            first = build_output_path(source, folder)
            second = build_output_path(source, folder)

            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, folder)
            self.assertTrue(first.name.startswith("clip_clean_"))
            self.assertEqual(first.suffix, ".mp4")

    def test_cli_default_output_path_uses_unique_clean_name(self) -> None:
        first = Path(build_default_output_path("C:/tmp/clip.mp4"))
        second = Path(build_default_output_path("C:/tmp/clip.mp4"))

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, Path("C:/tmp"))
        self.assertTrue(first.name.startswith("clip_clean_"))
        self.assertEqual(first.suffix, ".mp4")

    def test_build_finds_real_chocolatey_ffmpeg_before_path_shim(self) -> None:
        real = Path("C:/ProgramData/chocolatey/lib/ffmpeg/tools/ffmpeg/bin/ffmpeg.exe")
        shim = Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe")

        def fake_exists(path: Path) -> bool:
            return path in {real, shim}

        with (
            mock.patch("build_exe.os.name", "nt"),
            mock.patch("build_exe.os.environ.get", return_value=None),
            mock.patch("build_exe.ROOT", Path("D:/repo")),
            mock.patch("build_exe.shutil.which", return_value=str(shim)),
            mock.patch("pathlib.Path.exists", fake_exists),
            mock.patch("pathlib.Path.resolve", lambda self: self),
        ):
            self.assertEqual(find_ffmpeg(), real)

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
            draw_gemini_sparkle(frame, center, 52, (242, 242, 242))
            frames.append(frame.astype(np.float32))

        mean_frame = np.mean(np.stack(frames), axis=0).astype(np.uint8)
        detected = _auto_detect(frames, mean_frame, width, height, (WATERMARK_GEMINI,))

        self.assertIsNotNone(detected)
        x, y, w, h = detected
        self.assertLessEqual(x, center[0])
        self.assertLessEqual(y, center[1])
        self.assertGreaterEqual(x + w, center[0])
        self.assertGreaterEqual(y + h, center[1])

    def test_gemini_auto_detect_ignores_center_right_false_positive_on_landscape_video(self) -> None:
        width, height = 1280, 720
        frames = []
        center = (1184, 640)
        for _ in range(8):
            frame = np.full((height, width, 3), (95, 118, 128), dtype=np.uint8)
            cv2.circle(frame, (720, 420), 24, (238, 238, 238), -1, cv2.LINE_AA)
            draw_gemini_sparkle(frame, center, 54, (242, 242, 242))
            frames.append(frame.astype(np.float32))

        mean_frame = np.mean(np.stack(frames), axis=0).astype(np.uint8)
        detected = _auto_detect(frames, mean_frame, width, height, (WATERMARK_GEMINI,))

        self.assertIsNotNone(detected)
        x, y, w, h = detected
        self.assertLessEqual(x, center[0])
        self.assertLessEqual(y, center[1])
        self.assertGreaterEqual(x + w, center[0])
        self.assertGreaterEqual(y + h, center[1])

    def test_gemini_auto_detect_prefers_sparkle_shape_over_farther_right_blob(self) -> None:
        width, height = 1920, 1080
        frames = []
        center = (1775, 935)
        for _ in range(8):
            frame = np.full((height, width, 3), (120, 132, 140), dtype=np.uint8)
            cv2.circle(frame, (1870, 945), 34, (232, 232, 232), -1, cv2.LINE_AA)
            draw_gemini_sparkle(frame, center, 68, (242, 242, 242))
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

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from seedance_gui import (
    SeedanceApp,
    build_centered_geometry,
    build_output_path,
    choose_window_size,
    get_ui_text,
    normalize_path,
    parse_region,
)


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
        self.assertEqual((width, height), (900, 820))
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


if __name__ == "__main__":
    unittest.main()

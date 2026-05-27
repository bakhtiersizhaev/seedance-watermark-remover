#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import ctypes
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from watermark_remover import WATERMARK_GEMINI, WATERMARK_SEEDANCE, remove_watermark

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

APP_NAME = "Seedance Watermark Remover"
APP_VERSION = "1.1.0"
GITHUB_URL = "https://github.com/bakhtiersizhaev/seedance-watermark-remover"
TELEGRAM_CHANNEL_URL = "https://t.me/ai2key"
TELEGRAM_AUTHOR_URL = "https://t.me/bakhtier_sizhaev"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

WINDOW_BG = "#080d14"
CARD_BG = "#101823"
CARD_BG_SOFT = "#151f2c"
INPUT_BG = "#0d1420"
TEXT = "#f4f8fb"
MUTED = "#93a4b7"
SUBTLE = "#607086"
ACCENT = "#58a6ff"
ACCENT_HOVER = "#74bcff"
SUCCESS = "#5ee2a0"
DANGER = "#ff6b6b"
BORDER = "#263447"

PREFERRED_WINDOW_WIDTH = 900
PREFERRED_WINDOW_HEIGHT = 1200
MIN_WINDOW_WIDTH = 760
MIN_WINDOW_HEIGHT = 760
SCREEN_MARGIN = 48


def enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def choose_window_size(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    """Return a comfortable launch size and safe minimum size for the current screen."""
    available_width = max(640, screen_width - SCREEN_MARGIN)
    available_height = max(560, screen_height - SCREEN_MARGIN)
    width = min(PREFERRED_WINDOW_WIDTH, available_width)
    height = min(PREFERRED_WINDOW_HEIGHT, available_height)
    min_width = min(MIN_WINDOW_WIDTH, width)
    min_height = min(MIN_WINDOW_HEIGHT, height)
    return width, height, min_width, min_height


def build_centered_geometry(screen_width: int, screen_height: int) -> str:
    width, height, _, _ = choose_window_size(screen_width, screen_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    return f"{width}x{height}+{x}+{y}"


LANGUAGE_NAMES = ("English", "Русский", "中文")
LANGUAGE_CODES = {"English": "en", "Русский": "ru", "中文": "zh"}
DEFAULT_LANGUAGE = "English"

UI_TEXT = {
    "en": {
        "app_title": "Seedance Cleaner",
        "subtitle": "Remove small video watermarks locally. No upload, no account, no external service.",
        "language_label": "Language",
        "version": "Version {version}",
        "drop_title": "Drop video here",
        "drop_subtitle": "or paste a copied video with Ctrl+V",
        "browse": "Browse video",
        "paste": "Paste",
        "choose_output": "Choose output",
        "output_label": "Output",
        "output_empty": "Output will be created next to the input video.",
        "manual_region": "Manual region",
        "region_placeholder": "x,y,w,h — empty = auto-detect",
        "watermark_types": "Watermarks to remove",
        "seedance_type": "Seedance",
        "gemini_type": "Gemini sparkle",
        "no_watermark_type": "Select at least one watermark type.",
        "open_result_folder": "Open result folder",
        "remove": "Remove watermark",
        "processing": "Processing...",
        "ready": "Ready",
        "ready_log": "Ready. Fast OpenCV TELEA preset is selected.",
        "choose_video_title": "Choose video",
        "choose_output_title": "Choose output folder",
        "video_files": "Video files",
        "all_files": "All files",
        "clipboard_missing": "Clipboard does not contain a video path.",
        "no_video": "No supported video file found.",
        "unsupported": "Unsupported or missing video file.",
        "selected": "Video selected.",
        "choose_first": "Choose a video first.",
        "invalid_region": "Manual region must be x,y,w,h.",
        "ffmpeg_missing": "ffmpeg.exe was not found. Rebuild the portable app with bundled ffmpeg.exe.",
        "processing_status": "Processing locally. Keep this window open.",
        "detecting": "Detecting watermark region...",
        "reassembling": "Reassembling final MP4 with original audio...",
        "done": "Done. Clean video is ready.",
        "failed": "Failed. Check the log; try manual region if auto-detection failed.",
        "inpainting": "Inpainting frames {current}/{total}...",
        "made_by": "GitHub, made by Bakhtier Sizhaev",
        "telegram_channel": "Telegram channel: ai2key",
        "telegram_contact": "Author contact: bakhtier_sizhaev",
    },
    "ru": {
        "app_title": "Seedance Cleaner",
        "subtitle": "Удаляет небольшие водяные знаки локально. Без загрузки, аккаунта и внешнего сервиса.",
        "language_label": "Язык",
        "version": "Версия {version}",
        "drop_title": "Перетащите видео сюда",
        "drop_subtitle": "или вставьте скопированное видео через Ctrl+V",
        "browse": "Выбрать видео",
        "paste": "Вставить",
        "choose_output": "Папка результата",
        "output_label": "Результат",
        "output_empty": "Готовое видео будет создано рядом с исходным файлом.",
        "manual_region": "Область вручную",
        "region_placeholder": "x,y,w,h — пусто = автоопределение",
        "watermark_types": "Какие водяные знаки удалять",
        "seedance_type": "Seedance",
        "gemini_type": "Gemini звезда",
        "no_watermark_type": "Выберите хотя бы один тип водяного знака.",
        "open_result_folder": "Открыть папку",
        "remove": "Удалить водяной знак",
        "processing": "Обработка...",
        "ready": "Готово",
        "ready_log": "Готово. Выбран быстрый OpenCV TELEA режим.",
        "choose_video_title": "Выберите видео",
        "choose_output_title": "Выберите папку результата",
        "video_files": "Видео файлы",
        "all_files": "Все файлы",
        "clipboard_missing": "В буфере обмена нет пути к видео.",
        "no_video": "Поддерживаемое видео не найдено.",
        "unsupported": "Файл не найден или формат не поддерживается.",
        "selected": "Видео выбрано.",
        "choose_first": "Сначала выберите видео.",
        "invalid_region": "Область вручную должна быть в формате x,y,w,h.",
        "ffmpeg_missing": "ffmpeg.exe не найден. Пересоберите portable-приложение с ffmpeg.exe внутри.",
        "processing_status": "Обработка локально. Не закрывайте окно.",
        "detecting": "Определяю область водяного знака...",
        "reassembling": "Собираю итоговый MP4 с исходным звуком...",
        "done": "Готово. Очищенное видео создано.",
        "failed": "Ошибка. Проверьте лог; если автоопределение не помогло, задайте область вручную.",
        "inpainting": "Обработка кадров {current}/{total}...",
        "made_by": "GitHub, сделано Bakhtier Sizhaev",
        "telegram_channel": "Telegram-канал: ai2key",
        "telegram_contact": "Контакт автора: bakhtier_sizhaev",
    },
    "zh": {
        "app_title": "Seedance Cleaner",
        "subtitle": "在本机移除小型视频水印。无需上传、账号或外部服务。",
        "language_label": "语言",
        "version": "版本 {version}",
        "drop_title": "将视频拖到这里",
        "drop_subtitle": "或用 Ctrl+V 粘贴已复制的视频",
        "browse": "选择视频",
        "paste": "粘贴",
        "choose_output": "输出文件夹",
        "output_label": "输出",
        "output_empty": "处理后的视频会创建在原视频旁边。",
        "manual_region": "手动区域",
        "region_placeholder": "x,y,w,h — 留空 = 自动检测",
        "watermark_types": "要移除的水印",
        "seedance_type": "Seedance",
        "gemini_type": "Gemini 星形标记",
        "no_watermark_type": "请至少选择一种水印类型。",
        "open_result_folder": "打开结果文件夹",
        "remove": "移除水印",
        "processing": "处理中...",
        "ready": "就绪",
        "ready_log": "就绪。已选择快速 OpenCV TELEA 模式。",
        "choose_video_title": "选择视频",
        "choose_output_title": "选择输出文件夹",
        "video_files": "视频文件",
        "all_files": "所有文件",
        "clipboard_missing": "剪贴板中没有视频路径。",
        "no_video": "未找到支持的视频文件。",
        "unsupported": "文件不存在或格式不支持。",
        "selected": "已选择视频。",
        "choose_first": "请先选择视频。",
        "invalid_region": "手动区域格式必须是 x,y,w,h。",
        "ffmpeg_missing": "未找到 ffmpeg.exe。请重新构建包含 ffmpeg.exe 的便携版应用。",
        "processing_status": "正在本机处理。请保持窗口打开。",
        "detecting": "正在检测水印区域...",
        "reassembling": "正在用原音频重新生成 MP4...",
        "done": "完成。已创建清理后的视频。",
        "failed": "失败。请查看日志；如果自动检测失败，请尝试手动区域。",
        "inpainting": "正在处理帧 {current}/{total}...",
        "made_by": "GitHub，由 Bakhtier Sizhaev 制作",
        "telegram_channel": "Telegram 频道：ai2key",
        "telegram_contact": "作者联系方式：bakhtier_sizhaev",
    },
}


def get_ui_text(language: str, key: str, **values: object) -> str:
    code = LANGUAGE_CODES.get(language, language)
    bundle = UI_TEXT.get(code, UI_TEXT["en"])
    template = bundle.get(key, UI_TEXT["en"][key])
    return template.format(**values) if values else template


def find_resource(*parts: str) -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir.joinpath(*parts))
        candidates.append(exe_dir.joinpath("_internal", *parts))
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS).joinpath(*parts))  # type: ignore[attr-defined]
    candidates.append(Path(__file__).resolve().parent.joinpath(*parts))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


class QueueWriter:
    def __init__(self, events: queue.Queue[tuple]) -> None:
        self.events = events

    def write(self, text: str) -> int:
        if not text:
            return 0
        for match in re.finditer(r"(\d+)\s*/\s*(\d+)", text):
            current, total = int(match.group(1)), int(match.group(2))
            if total:
                self.events.put(("progress", current, total))
        for chunk in text.replace("\r", "\n").split("\n"):
            line = chunk.strip()
            if line and not re.fullmatch(r"\d+\s*/\s*\d+", line):
                self.events.put(("log", line))
        return len(text)

    def flush(self) -> None:
        pass


class SeedanceApp:
    def __init__(self, hidden: bool = False) -> None:
        enable_windows_dpi_awareness()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        root_factory = TkinterDnD.Tk if TkinterDnD else ctk.CTk
        self.root = root_factory()
        self.root.title(APP_NAME)
        self._apply_initial_window_bounds()
        self.root.configure(bg=WINDOW_BG)
        self._set_icon()
        if hidden:
            self.root.withdraw()

        self.events: queue.Queue[tuple] = queue.Queue()
        self.busy = False
        self.language = tk.StringVar(value=DEFAULT_LANGUAGE)
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.region = tk.StringVar()
        self.remove_seedance = tk.BooleanVar(value=True)
        self.remove_gemini = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value=self._text("ready"))
        self.progress_label = tk.StringVar(value="")
        self.output_preview = tk.StringVar(value=self._text("output_empty"))
        self.open_done = tk.BooleanVar(value=True)

        self._ui()
        self.root.bind("<Control-v>", lambda _event: self.paste_video())
        self.root.bind("<Control-V>", lambda _event: self.paste_video())
        self.root.bind("<Configure>", self._resize_text_wraps)
        self.root.after(100, self._drain)

    def _text(self, key: str, **values: object) -> str:
        return get_ui_text(self.language.get(), key, **values)

    def _apply_initial_window_bounds(self) -> None:
        screen_width = max(1, self.root.winfo_screenwidth())
        screen_height = max(1, self.root.winfo_screenheight())
        _, _, min_width, min_height = choose_window_size(screen_width, screen_height)
        self.root.geometry(build_centered_geometry(screen_width, screen_height))
        self.root.minsize(min_width, min_height)

    def _set_icon(self) -> None:
        icon = find_resource("assets", "seedance-cleaner.ico")
        if icon:
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass

    def _ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(self.root, fg_color=WINDOW_BG, corner_radius=0)
        shell.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(7, weight=1)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        mark = ctk.CTkFrame(
            header, width=44, height=44, fg_color=CARD_BG_SOFT, corner_radius=15, border_width=1, border_color=BORDER
        )
        mark.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        mark.grid_propagate(False)
        ctk.CTkLabel(mark, text="✦", text_color=ACCENT, font=ctk.CTkFont(size=22, weight="bold")).place(
            relx=0.5, rely=0.48, anchor="center"
        )

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=1, sticky="ew")
        self.title_label = ctk.CTkLabel(
            title_box,
            text=self._text("app_title"),
            text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=24, weight="bold"),
            anchor="w",
        )
        self.title_label.pack(anchor="w")
        self.subtitle_label = ctk.CTkLabel(
            title_box,
            text=self._text("subtitle"),
            text_color=MUTED,
            font=ctk.CTkFont(size=13),
            anchor="w",
            justify="left",
        )
        self.subtitle_label.pack(anchor="w", pady=(3, 0), fill="x")

        language_box = ctk.CTkFrame(header, fg_color="transparent")
        language_box.grid(row=0, column=2, sticky="ne", padx=(12, 0))
        self.language_label = ctk.CTkLabel(
            language_box, text=self._text("language_label"), text_color=MUTED, font=ctk.CTkFont(size=12)
        )
        self.language_label.pack(anchor="e", pady=(0, 4))
        self.language_menu = ctk.CTkOptionMenu(
            language_box,
            values=list(LANGUAGE_NAMES),
            variable=self.language,
            command=lambda _choice: self._apply_language(),
            fg_color=CARD_BG_SOFT,
            button_color=BORDER,
            button_hover_color=ACCENT,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=CARD_BG_SOFT,
            dropdown_text_color=TEXT,
            text_color=TEXT,
            width=132,
            height=34,
            corner_radius=12,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.language_menu.pack(anchor="e")
        self.version_label = ctk.CTkLabel(
            language_box,
            text=self._text("version", version=APP_VERSION),
            text_color=SUBTLE,
            font=ctk.CTkFont(size=11),
        )
        self.version_label.pack(anchor="e", pady=(5, 0))

        self.drop = ctk.CTkFrame(
            shell, height=124, fg_color=CARD_BG, corner_radius=20, border_width=1, border_color=BORDER
        )
        self.drop.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        self.drop.grid_propagate(False)
        self.drop.grid_columnconfigure(0, weight=1)
        self.drop.bind("<Button-1>", lambda _event: self.browse_video())
        self.drop_title_label = ctk.CTkLabel(
            self.drop,
            text=self._text("drop_title"),
            text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=18, weight="bold"),
        )
        self.drop_title_label.grid(row=0, column=0, pady=(12, 1), padx=16, sticky="ew")
        self.drop_subtitle_label = ctk.CTkLabel(
            self.drop,
            text=self._text("drop_subtitle"),
            text_color=MUTED,
            font=ctk.CTkFont(size=13),
            justify="center",
        )
        self.drop_subtitle_label.grid(row=1, column=0, padx=18, sticky="ew")
        self.input_path_label = ctk.CTkLabel(
            self.drop,
            textvariable=self.input_path,
            text_color=ACCENT,
            font=ctk.CTkFont(size=12),
            wraplength=680,
            justify="center",
        )
        self.input_path_label.grid(row=2, column=0, padx=18, pady=(5, 0), sticky="ew")
        if DND_FILES:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._drop)

        actions = ctk.CTkFrame(shell, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for column in range(3):
            actions.grid_columnconfigure(column, weight=1, uniform="actions")
        self.browse_btn = self._button(actions, self._text("browse"), self.browse_video, secondary=True)
        self.browse_btn.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.paste_btn = self._button(actions, self._text("paste"), self.paste_video, secondary=True)
        self.paste_btn.grid(row=0, column=1, padx=4, sticky="ew")
        self.output_btn = self._button(actions, self._text("choose_output"), self.choose_output, secondary=True)
        self.output_btn.grid(row=0, column=2, padx=(8, 0), sticky="ew")

        settings = ctk.CTkFrame(shell, fg_color=CARD_BG, corner_radius=24, border_width=1, border_color=BORDER)
        settings.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        settings.grid_columnconfigure(0, weight=1)
        settings.grid_columnconfigure(1, weight=0)

        self.output_section_label = self._section_label(settings, self._text("output_label"))
        self.output_section_label.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 2))
        self.output_preview_label = ctk.CTkLabel(
            settings,
            textvariable=self.output_preview,
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
            wraplength=620,
            anchor="w",
            justify="left",
        )
        self.output_preview_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        self.types_section_label = self._section_label(settings, self._text("watermark_types"))
        self.types_section_label.grid(row=2, column=0, sticky="w", padx=18)
        provider_row = ctk.CTkFrame(settings, fg_color="transparent")
        provider_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(7, 10))
        self.seedance_checkbox = ctk.CTkCheckBox(
            provider_row,
            text=self._text("seedance_type"),
            variable=self.remove_seedance,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.seedance_checkbox.pack(side="left", padx=(0, 18))
        self.gemini_checkbox = ctk.CTkCheckBox(
            provider_row,
            text=self._text("gemini_type"),
            variable=self.remove_gemini,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.gemini_checkbox.pack(side="left")

        self.region_section_label = self._section_label(settings, self._text("manual_region"))
        self.region_section_label.grid(row=4, column=0, sticky="w", padx=18)
        self.region_entry = ctk.CTkEntry(
            settings,
            textvariable=self.region,
            fg_color=INPUT_BG,
            border_color=BORDER,
            border_width=1,
            corner_radius=14,
            text_color=TEXT,
            placeholder_text=self._text("region_placeholder"),
            placeholder_text_color=SUBTLE,
            font=ctk.CTkFont(family="Cascadia Mono", size=13),
            height=40,
        )
        self.region_entry.grid(row=5, column=0, sticky="ew", padx=18, pady=(7, 14))
        self.open_done_checkbox = ctk.CTkCheckBox(
            settings,
            text=self._text("open_result_folder"),
            variable=self.open_done,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
        )
        self.open_done_checkbox.grid(row=5, column=1, sticky="w", padx=(10, 18), pady=(7, 14))

        self.run_btn = self._button(shell, self._text("remove"), self.start, secondary=False)
        self.run_btn.grid(row=4, column=0, sticky="ew", pady=(0, 8))

        status_row = ctk.CTkFrame(shell, fg_color="transparent")
        status_row.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        status_row.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(
            status_row, height=12, corner_radius=10, fg_color=CARD_BG_SOFT, progress_color=ACCENT
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)
        ctk.CTkLabel(
            status_row, textvariable=self.progress_label, text_color=MUTED, font=ctk.CTkFont(size=12), width=52
        ).grid(row=0, column=1, padx=(12, 0))

        self.status_label = ctk.CTkLabel(
            shell, textvariable=self.status, text_color=MUTED, font=ctk.CTkFont(size=12), anchor="w", justify="left"
        )
        self.status_label.grid(row=6, column=0, sticky="ew")
        self.log = ctk.CTkTextbox(
            shell,
            height=60,
            fg_color="#070b11",
            text_color="#d7e0ea",
            border_width=1,
            border_color=BORDER,
            corner_radius=18,
            font=ctk.CTkFont(family="Cascadia Mono", size=11),
            wrap="word",
        )
        self.log.grid(row=7, column=0, sticky="nsew")
        self.log.configure(state="disabled")
        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        for column in range(3):
            footer.grid_columnconfigure(column, weight=1, uniform="footer")
        self.github_link = self._link_label(footer, self._text("made_by"), GITHUB_URL)
        self.github_link.grid(row=0, column=0, sticky="w")
        self.telegram_channel_link = self._link_label(footer, self._text("telegram_channel"), TELEGRAM_CHANNEL_URL)
        self.telegram_channel_link.grid(row=0, column=1)
        self.telegram_contact_link = self._link_label(footer, self._text("telegram_contact"), TELEGRAM_AUTHOR_URL)
        self.telegram_contact_link.grid(row=0, column=2, sticky="e")
        self._log(self._text("ready_log"))
        self._resize_text_wraps()

    def _apply_language(self) -> None:
        self.title_label.configure(text=self._text("app_title"))
        self.subtitle_label.configure(text=self._text("subtitle"))
        self.language_label.configure(text=self._text("language_label"))
        self.version_label.configure(text=self._text("version", version=APP_VERSION))
        self.drop_title_label.configure(text=self._text("drop_title"))
        self.drop_subtitle_label.configure(text=self._text("drop_subtitle"))
        self.browse_btn.configure(text=self._text("browse"))
        self.paste_btn.configure(text=self._text("paste"))
        self.output_btn.configure(text=self._text("choose_output"))
        self.output_section_label.configure(text=self._text("output_label"))
        self.types_section_label.configure(text=self._text("watermark_types"))
        self.seedance_checkbox.configure(text=self._text("seedance_type"))
        self.gemini_checkbox.configure(text=self._text("gemini_type"))
        self.region_section_label.configure(text=self._text("manual_region"))
        self.region_entry.configure(placeholder_text=self._text("region_placeholder"))
        self.open_done_checkbox.configure(text=self._text("open_result_folder"))
        self.github_link.configure(text=self._text("made_by"))
        self.telegram_channel_link.configure(text=self._text("telegram_channel"))
        self.telegram_contact_link.configure(text=self._text("telegram_contact"))
        self.run_btn.configure(text=self._text("processing") if self.busy else self._text("remove"))
        if not self.input_path.get():
            self.output_preview.set(self._text("output_empty"))
        if not self.busy:
            self.status.set(self._text("ready"))
        self._resize_text_wraps()

    def _resize_text_wraps(self, event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not self.root:
            return
        width = max(MIN_WINDOW_WIDTH, self.root.winfo_width())
        content_width = max(360, width - 120)
        self.subtitle_label.configure(wraplength=content_width)
        self.drop_subtitle_label.configure(wraplength=content_width)
        self.input_path_label.configure(wraplength=content_width)
        self.output_preview_label.configure(wraplength=content_width)
        self.status_label.configure(wraplength=content_width)

    def _section_label(self, parent: tk.Widget, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold"), anchor="w")

    def _button(self, parent: tk.Widget, text: str, command, secondary: bool) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=CARD_BG_SOFT if secondary else ACCENT,
            hover_color=BORDER if secondary else ACCENT_HOVER,
            text_color=TEXT if secondary else "#06111f",
            corner_radius=16,
            border_width=1 if secondary else 0,
            border_color=BORDER,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
        )

    def _link_label(self, parent: tk.Widget, text: str, url: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=text,
            text_color=ACCENT,
            font=ctk.CTkFont(size=11, underline=True),
            cursor="hand2",
        )
        label.bind("<Button-1>", lambda _event: webbrowser.open(url))
        return label

    def _drop(self, event) -> None:
        self._pick_first(parse_drop_paths(self.root, event.data))

    def browse_video(self) -> None:
        path = filedialog.askopenfilename(
            title=self._text("choose_video_title"),
            filetypes=[
                (self._text("video_files"), "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
                (self._text("all_files"), "*.*"),
            ],
        )
        if path:
            self.set_video(Path(path))

    def choose_output(self) -> None:
        initial = self.output_dir.get() or (str(Path(self.input_path.get()).parent) if self.input_path.get() else None)
        folder = filedialog.askdirectory(title=self._text("choose_output_title"), initialdir=initial)
        if folder:
            self.output_dir.set(folder)
            self._refresh_output()

    def paste_video(self) -> None:
        paths = clipboard_video_paths(self.root)
        if not paths:
            self._status(self._text("clipboard_missing"), DANGER)
            return
        self._pick_first(paths)

    def _pick_first(self, paths: list[Path]) -> None:
        for path in paths:
            if is_video(path):
                self.set_video(path)
                return
        self._status(self._text("no_video"), DANGER)

    def set_video(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not is_video(path):
            self._status(self._text("unsupported"), DANGER)
            return
        self.input_path.set(str(path))
        if not self.output_dir.get():
            self.output_dir.set(str(path.parent))
        self._refresh_output()
        self._status(self._text("selected"), SUCCESS)
        self._log(f"Input: {path}")

    def _refresh_output(self) -> None:
        if not self.input_path.get():
            self.output_preview.set(self._text("output_empty"))
            return
        output = build_output_path(
            Path(self.input_path.get()), Path(self.output_dir.get() or Path(self.input_path.get()).parent)
        )
        self.output_preview.set(str(output))

    def start(self) -> None:
        if self.busy:
            return
        if not self.input_path.get():
            self._status(self._text("choose_first"), DANGER)
            return
        region = parse_region(self.region.get())
        if self.region.get().strip() and region is None:
            self._status(self._text("invalid_region"), DANGER)
            return
        watermark_types = self._selected_watermark_types()
        if not watermark_types:
            self._status(self._text("no_watermark_type"), DANGER)
            return
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            messagebox.showerror(APP_NAME, self._text("ffmpeg_missing"))
            return

        input_path = Path(self.input_path.get())
        out_dir = Path(self.output_dir.get() or input_path.parent)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = build_output_path(input_path, out_dir)
        os.environ["PATH"] = str(ffmpeg.parent) + os.pathsep + os.environ.get("PATH", "")

        self.busy = True
        self.run_btn.configure(state="disabled", text=self._text("processing"))
        self.progress.set(0)
        self.progress_label.set("0%")
        self._status(self._text("processing_status"), ACCENT)
        self._log(f"Output: {output_path}")
        self._log(f"Using ffmpeg: {ffmpeg}")
        self._log(f"Watermark types: {', '.join(watermark_types)}")
        threading.Thread(
            target=self._worker,
            args=(input_path, output_path, region, watermark_types),
            daemon=True,
        ).start()

    def _worker(
        self,
        input_path: Path,
        output_path: Path,
        region: tuple[int, int, int, int] | None,
        watermark_types: tuple[str, ...],
    ) -> None:
        writer = QueueWriter(self.events)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                ok = remove_watermark(
                    str(input_path), str(output_path), manual_region=region, watermark_types=watermark_types
                )
            self.events.put(("done", ok, str(output_path)))
        except Exception as exc:
            self.events.put(("error", repr(exc)))

    def _selected_watermark_types(self) -> tuple[str, ...]:
        selected = []
        if self.remove_gemini.get():
            selected.append(WATERMARK_GEMINI)
        if self.remove_seedance.get():
            selected.append(WATERMARK_SEEDANCE)
        return tuple(selected)

    def _drain(self) -> None:
        try:
            while True:
                item = self.events.get_nowait()
                if item[0] == "log":
                    self._log(item[1])
                    self._status_from_log(item[1])
                elif item[0] == "progress":
                    current, total = item[1], item[2]
                    pct = max(0, min(100, int(current * 100 / total)))
                    self.progress.set(pct / 100)
                    self.progress_label.set(f"{pct}%")
                    self.status.set(self._text("inpainting", current=current, total=total))
                elif item[0] == "done":
                    self._finish(item[1], Path(item[2]))
                elif item[0] == "error":
                    self._log(item[1])
                    self._finish(False, None)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _status_from_log(self, line: str) -> None:
        if line.startswith("Video:"):
            self._status(line, MUTED)
        elif "Sampling frames" in line:
            self._status(self._text("detecting"), ACCENT)
        elif line.startswith("Detected watermark") or line.startswith("Using manual"):
            self._status(line, SUCCESS)
        elif "Reassembling" in line:
            self._status(self._text("reassembling"), ACCENT)
        elif line.startswith("Error:"):
            self._status(line, DANGER)

    def _finish(self, ok: bool, output_path: Path | None) -> None:
        self.busy = False
        self.run_btn.configure(state="normal", text=self._text("remove"))
        if ok and output_path:
            self.progress.set(1)
            self.progress_label.set("100%")
            self._status(self._text("done"), SUCCESS)
            self._log(f"Done: {output_path}")
            if self.open_done.get():
                open_folder(output_path.parent)
        else:
            self._status(self._text("failed"), DANGER)
            self.progress_label.set("")

    def _status(self, text: str, color: str) -> None:
        self.status.set(text)
        self.status_label.configure(text_color=color)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self) -> None:
        self.root.mainloop()

    def destroy(self) -> None:
        self.root.destroy()


def parse_region(value: str) -> tuple[int, int, int, int] | None:
    if not value.strip():
        return None
    try:
        parts = tuple(int(part.strip()) for part in value.split(","))
    except ValueError:
        return None
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0 or any(part < 0 for part in parts):
        return None
    return parts


def is_video(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def parse_drop_paths(root: tk.Tk, raw: str) -> list[Path]:
    try:
        values = root.tk.splitlist(raw)
    except tk.TclError:
        values = raw.split()
    return [normalize_path(value) for value in values if value]


def normalize_path(value: str) -> Path:
    cleaned = value.strip().strip("{}\"'")
    if cleaned.startswith("file:///"):
        cleaned = cleaned[8:]
    elif cleaned.startswith("file://"):
        cleaned = cleaned[7:]
    return Path(cleaned)


def clipboard_video_paths(root: tk.Tk) -> list[Path]:
    paths = windows_clipboard_files()
    if paths:
        return paths
    try:
        text = root.clipboard_get().strip()
    except tk.TclError:
        return []
    return [normalize_path(line) for line in re.split(r"[\r\n]+", text) if line.strip()]


def windows_clipboard_files() -> list[Path]:
    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    CF_HDROP = 15
    if not user32.OpenClipboard(None):
        return []
    try:
        handle = user32.GetClipboardData(CF_HDROP)
        if not handle:
            return []
        count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        paths = []
        for index in range(count):
            length = shell32.DragQueryFileW(handle, index, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(handle, index, buffer, length + 1)
            paths.append(Path(buffer.value))
        return paths
    finally:
        user32.CloseClipboard()


def build_output_path(input_path: Path, output_dir: Path) -> Path:
    candidate = output_dir / f"{input_path.stem}_clean.mp4"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = output_dir / f"{input_path.stem}_clean_{index}.mp4"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Too many existing output files.")


def find_ffmpeg() -> Path | None:
    bases: list[Path] = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).resolve().parent)
    if hasattr(sys, "_MEIPASS"):
        bases.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    bases.append(Path(__file__).resolve().parent)
    for base in bases:
        for rel in ("ffmpeg.exe", "ffmpeg", "_internal/ffmpeg.exe", "_internal/ffmpeg"):
            candidate = base / rel
            if candidate.exists():
                return candidate
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def open_folder(folder: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception:
        pass


def run_self_test() -> int:
    import cv2  # noqa: F401
    import numpy as np  # noqa: F401

    app = SeedanceApp(hidden=True)
    try:
        app.root.update_idletasks()
        app.root.update()
        parse_region("1,2,3,4")
        build_output_path(Path("input.mp4"), Path.cwd())
        return 0
    finally:
        app.destroy()


def run_smoke_process() -> int:
    import tempfile

    import cv2
    import numpy as np

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("smoke: ffmpeg not found", file=sys.stderr)
        return 2
    os.environ["PATH"] = str(ffmpeg.parent) + os.pathsep + os.environ.get("PATH", "")

    with tempfile.TemporaryDirectory(prefix="seedance_gui_smoke_") as tmp:
        tmp_dir = Path(tmp)
        input_path = tmp_dir / "smoke_input.mp4"
        output_path = tmp_dir / "smoke_output.mp4"
        width, height, fps = 160, 96, 12
        writer = cv2.VideoWriter(str(input_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            print("smoke: could not create input video", file=sys.stderr)
            return 3
        for frame_index in range(12):
            frame = np.full((height, width, 3), (36 + frame_index, 44, 55), dtype=np.uint8)
            cv2.putText(frame, "AI", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 2)
            writer.write(frame)
        writer.release()

        ok = remove_watermark(str(input_path), str(output_path), manual_region=(0, 0, 50, 34))
        if not ok or not output_path.exists() or output_path.stat().st_size <= 0:
            print("smoke: processing failed", file=sys.stderr)
            return 4
        print(f"smoke: ok {output_path.stat().st_size} bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--self-test", action="store_true", help="Create and destroy the GUI, then exit.")
    parser.add_argument(
        "--smoke-process", action="store_true", help="Run a tiny end-to-end processing smoke test, then exit."
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()
    if args.smoke_process:
        return run_smoke_process()
    SeedanceApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

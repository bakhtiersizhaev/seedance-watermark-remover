# Seedance Watermark Remover GUI

Seedance Watermark Remover is a portable Windows desktop app for local video watermark cleanup. It is for users who want to remove a small static corner mark from an MP4 without installing Python, opening an online editor, or sending the video outside their computer.

## When the GUI is the right choice

Use the desktop app when:

- the mark is small and static;
- the mark is near a video corner;
- you want a clean output copy while keeping the original file untouched;
- you prefer drag-and-drop over command-line usage;
- you need a portable Windows folder that can be shared as a ZIP.

Large moving overlays, center-screen marks, and complex transparent objects may still need manual editing in a video editor.

## User flow

1. Open `SeedanceWatermarkRemover.exe` from the extracted portable folder.
2. Add a video by drag-and-drop, Ctrl+V after copying a video file/path, or **Browse video**.
3. Optionally choose an output folder. By default, the app saves next to the input video as `<name>_clean.mp4`.
4. Leave **Manual region** empty for auto-detect, or enter `x,y,w,h` if the app should clean a specific area.
5. Click **Remove watermark** and wait for the progress bar to finish.
6. Check the new output file. The original video is left untouched.

## When manual region helps

Use manual region when auto-detection chooses the wrong corner, misses very thin text, or sees too much movement near the badge. The format is `x,y,width,height` in pixels.

## Distribution

Ship the whole folder:

```text
dist/SeedanceWatermarkRemover/
```

Do not send only the `.exe`; it needs the `_internal` folder with bundled runtime files, OpenCV, CustomTkinter, Tk support files, ffmpeg, and app assets.

For convenience, ship the generated Windows x64 portable release asset:

```text
dist/SeedanceWatermarkRemover-Windows-x64-portable.zip
```

This ZIP contains one top-level `SeedanceWatermarkRemover` folder. Users should extract the ZIP first, then run the EXE from the extracted folder.

## Branding assets

The original app mark is stored as an SVG source. PNG sizes and the Windows ICO are generated from the same mark and bundled into the portable build. The GitHub Pages site uses the same visual identity.

## Build checks

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m ruff check .
python -m unittest -v
python build_exe.py
```

The build script verifies both source and packaged app:

- `seedance_gui.py --self-test`
- `seedance_gui.py --smoke-process`
- packaged EXE self-test
- packaged EXE smoke-process
- extracted ZIP self-test
- extracted ZIP smoke-process

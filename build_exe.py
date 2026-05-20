#!/usr/bin/env python3
"""Build and verify the Windows portable GUI release artifact."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

APP_NAME = "SeedanceWatermarkRemover"
RELEASE_ZIP_NAME = f"{APP_NAME}-Windows-x64-portable.zip"
ROOT = Path(__file__).resolve().parent
PYTHON = Path(sys.executable)

VISIBLE_DOCS = ["README.md", "GUI_README.md", "LICENSE", "КАК_ЗАПУСТИТЬ.txt"]
RELEASE_ASSETS = [
    "assets/seedance-cleaner.ico",
    "assets/seedance-cleaner-icon.svg",
    "assets/seedance-cleaner-icon-256.png",
]

# These packages are not part of the CPU-only release. They can be present in a
# shared developer Python environment and must not leak into the portable build.
EXCLUDED_MODULES = [
    "accelerate",
    "aiohttp",
    "asyncpg",
    "av",
    "boto3",
    "botocore",
    "diffusers",
    "fastapi",
    "flask",
    "grpc",
    "IPython",
    "jedi",
    "jupyter",
    "llvmlite",
    "matplotlib",
    "nbformat",
    "numba",
    "onnx",
    "onnxruntime",
    "opentelemetry",
    "pandas",
    "paramiko",
    "pyarrow",
    "pythonnet",
    "redis",
    "safetensors",
    "scipy",
    "sklearn",
    "torch",
    "torchaudio",
    "torchvision",
    "transformers",
    "triton",
    "xformers",
]

FORBIDDEN_BUNDLE_ENTRIES = [f"_internal/{module}" for module in EXCLUDED_MODULES]


def run(cmd: list[str], *, cwd: Path = ROOT) -> None:
    print("$", " ".join(str(part) for part in cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def find_ffmpeg() -> Path:
    local_ffmpeg = ROOT / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return local_ffmpeg.resolve()
    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if found:
        return Path(found).resolve()
    raise SystemExit("ffmpeg.exe not found. Put ffmpeg.exe in project root or on PATH.")


def clean_previous_outputs() -> None:
    for folder in (ROOT / "build", ROOT / "dist"):
        if folder.exists():
            shutil.rmtree(folder)
    legacy_spec = ROOT / f"{APP_NAME}.spec"
    if legacy_spec.exists():
        legacy_spec.unlink()
    legacy_zip = ROOT / RELEASE_ZIP_NAME
    if legacy_zip.exists():
        legacy_zip.unlink()


def build_pyinstaller(ffmpeg: Path) -> Path:
    separator = ";" if sys.platform.startswith("win") else ":"
    workpath = ROOT / "build" / "pyinstaller-work"
    specpath = ROOT / "build" / "pyinstaller-spec"
    args = [
        str(PYTHON),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        APP_NAME,
        "--workpath",
        str(workpath),
        "--specpath",
        str(specpath),
        "--add-binary",
        f"{ffmpeg}{separator}.",
        "--icon",
        str(ROOT / "assets" / "seedance-cleaner.ico"),
    ]
    for asset in RELEASE_ASSETS:
        args.extend(["--add-data", f"{ROOT / asset}{separator}{Path(asset).parent.as_posix()}"])
    for module in EXCLUDED_MODULES:
        args.extend(["--exclude-module", module])
    args.append("seedance_gui.py")
    run(args)

    exe = ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe"
    if not exe.exists():
        raise SystemExit(f"Build did not produce {exe}")
    return exe


def copy_visible_docs(app_dir: Path) -> None:
    for name in VISIBLE_DOCS:
        source = ROOT / name
        if not source.exists():
            raise SystemExit(f"Required release doc missing: {source}")
        shutil.copy2(source, app_dir / name)


def relative_paths(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


def validate_app_folder(app_dir: Path) -> None:
    required = [
        app_dir / f"{APP_NAME}.exe",
        app_dir / "_internal",
        app_dir / "_internal" / "ffmpeg.exe",
        app_dir / "_internal" / "assets" / "seedance-cleaner.ico",
        *(app_dir / name for name in VISIBLE_DOCS),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Portable app folder is incomplete:\n" + "\n".join(missing))

    rels = relative_paths(app_dir)
    forbidden = [
        entry
        for entry in FORBIDDEN_BUNDLE_ENTRIES
        if any(path == entry or path.startswith(entry + "/") for path in rels)
    ]
    if forbidden:
        raise SystemExit("Unexpected shared-env packages leaked into portable build:\n" + "\n".join(forbidden))


def create_release_zip(app_dir: Path) -> Path:
    zip_path = ROOT / "dist" / RELEASE_ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(app_dir.parent))
    if zip_path.stat().st_size <= 0:
        raise SystemExit(f"Release ZIP is empty: {zip_path}")
    return zip_path


def validate_release_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    if not names:
        raise SystemExit(f"Release ZIP has no entries: {zip_path}")
    top_levels = {name.split("/", 1)[0] for name in names if name.strip("/")}
    if top_levels != {APP_NAME}:
        raise SystemExit(f"Release ZIP must contain exactly one top-level {APP_NAME} folder; got {sorted(top_levels)}")

    required = [
        f"{APP_NAME}/{APP_NAME}.exe",
        f"{APP_NAME}/_internal/ffmpeg.exe",
        f"{APP_NAME}/_internal/assets/seedance-cleaner.ico",
        *(f"{APP_NAME}/{name}" for name in VISIBLE_DOCS),
    ]
    missing = [name for name in required if name not in names]
    if missing:
        raise SystemExit("Release ZIP is missing required entries:\n" + "\n".join(missing))

    forbidden = [
        name for name in names if name.startswith(f"{APP_NAME}/.venv/") or name.startswith(f"{APP_NAME}/venv/")
    ]
    forbidden += [
        name
        for name in names
        for entry in FORBIDDEN_BUNDLE_ENTRIES
        if name.startswith(f"{APP_NAME}/{entry}/") or name == f"{APP_NAME}/{entry}"
    ]
    if forbidden:
        raise SystemExit("Release ZIP contains forbidden entries:\n" + "\n".join(sorted(set(forbidden))[:50]))


def verify_extracted_zip(zip_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="seedance_release_extract_") as tmp:
        extract_root = Path(tmp)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        app_dir = extract_root / APP_NAME
        validate_app_folder(app_dir)
        exe = app_dir / f"{APP_NAME}.exe"
        run([str(exe), "--self-test"], cwd=app_dir)
        run([str(exe), "--smoke-process"], cwd=app_dir)


def main() -> int:
    ffmpeg = find_ffmpeg()
    print(f"Using ffmpeg: {ffmpeg}")

    run([str(PYTHON), "seedance_gui.py", "--self-test"])
    run([str(PYTHON), "seedance_gui.py", "--smoke-process"])

    clean_previous_outputs()
    exe = build_pyinstaller(ffmpeg)
    app_dir = exe.parent
    copy_visible_docs(app_dir)
    validate_app_folder(app_dir)

    run([str(exe), "--self-test"], cwd=app_dir)
    run([str(exe), "--smoke-process"], cwd=app_dir)

    zip_path = create_release_zip(app_dir)
    validate_release_zip(zip_path)
    verify_extracted_zip(zip_path)

    print(f"\nBuilt app folder: {app_dir}")
    print(f"Built release ZIP: {zip_path}")
    print("Ship the ZIP as the ready Windows x64 portable app; keep source code separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable


DEFAULT_LOADING_ASSET_TAG = "loading-assets-v1"
DEFAULT_LOADING_ASSET_NAME = "loading-assets-v1.zip"
DEFAULT_LOADING_ASSET_URL = f"https://github.com/ncsaky/BBall_Starting_Point/releases/download/{DEFAULT_LOADING_ASSET_TAG}/{DEFAULT_LOADING_ASSET_NAME}"


def install_loading_assets(
    root: str | Path,
    *,
    zip_path: str | Path | None = None,
    url: str = DEFAULT_LOADING_ASSET_URL,
    force: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    root_path = Path(root).resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    progress = progress or (lambda _message: None)
    downloaded_path: Path | None = None
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    try:
        if zip_path:
            asset_path = Path(zip_path).expanduser().resolve()
            source = str(asset_path)
            if not asset_path.exists():
                return {"status": "missing_zip", "path": str(asset_path)}
        else:
            temp_dir = tempfile.TemporaryDirectory()
            downloaded_path = Path(temp_dir.name) / DEFAULT_LOADING_ASSET_NAME
            source = url
            download_result = _download_file(url, downloaded_path, progress)
            if download_result["status"] != "downloaded":
                return download_result
            asset_path = downloaded_path

        extracted = _extract_zip(asset_path, root_path, force=force)
        extracted.update({"source": source, "root": str(root_path)})
        return extracted
    finally:
        if temp_dir:
            temp_dir.cleanup()


def _download_file(url: str, destination: Path, progress: Callable[[str], None]) -> dict[str, object]:
    progress(f"Downloading loading assets from {url}")
    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            copied = 0
            next_report = 25 * 1024 * 1024
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                copied += len(chunk)
                if copied >= next_report:
                    if total:
                        progress(f"Downloaded {copied // (1024 * 1024)} MB of {total // (1024 * 1024)} MB")
                    else:
                        progress(f"Downloaded {copied // (1024 * 1024)} MB")
                    next_report += 25 * 1024 * 1024
    except urllib.error.HTTPError as exc:
        return {
            "status": "download_failed",
            "url": url,
            "reason": f"HTTP {exc.code}",
            "help": "If the repository is private, download the release zip in your browser and rerun with --zip /path/to/loading-assets-v1.zip.",
        }
    except urllib.error.URLError as exc:
        return {"status": "download_failed", "url": url, "reason": str(exc.reason)}
    except OSError as exc:
        return {"status": "download_failed", "url": url, "reason": str(exc)}
    return {"status": "downloaded", "path": str(destination)}


def _extract_zip(asset_path: Path, root_path: Path, *, force: bool) -> dict[str, object]:
    if not zipfile.is_zipfile(asset_path):
        return {"status": "invalid_zip", "path": str(asset_path)}

    extracted = 0
    skipped = 0
    with zipfile.ZipFile(asset_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            destination = _safe_destination(root_path, info.filename)
            if destination is None:
                return {"status": "unsafe_zip", "path": info.filename}
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not force:
                skipped += 1
                continue
            with archive.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            extracted += 1

    return {"status": "installed", "path": str(asset_path), "files_extracted": extracted, "files_skipped": skipped}


def _safe_destination(root_path: Path, member_name: str) -> Path | None:
    destination = (root_path / member_name).resolve()
    try:
        destination.relative_to(root_path)
    except ValueError:
        return None
    return destination


def stderr_progress(message: str) -> None:
    print(message, file=sys.stderr)

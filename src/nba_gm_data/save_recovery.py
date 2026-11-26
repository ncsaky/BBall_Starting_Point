"""Portable, validated local save snapshots and atomic recovery publication.

Archives contain a JSON manifest and a SQLite backup, never a raw copy of a
live WAL database. Restore publishes a new history filename before switching
the manifest, so interruption cannot pair old JSON with replacement history.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
import zlib
from contextlib import closing, contextmanager
from typing import Any, BinaryIO

from .save_locking import fsync_directory, save_lock


BACKUP_FORMAT = "nba_gm_backup_v1"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
# Local recovery is file-backed, not a browser upload or an in-memory archive.
MAX_LOCAL_ARCHIVE_BYTES = 4 * 1024 * 1024 * 1024
MAX_LOCAL_EXPANDED_BYTES = 16 * 1024 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_MANIFEST_BYTES = 512 * 1024 * 1024


class SaveRecoveryError(ValueError):
    pass


SEASON_ARCHIVE_MEMBER = re.compile(r"^season-\d{4}-\d{2}\.json\.gz$")


def season_archive_member(label: str) -> str:
    return f"season-{label}.json.gz"


def previous_backup_path(path: str | Path) -> Path:
    target = Path(path)
    return target.with_name(target.name + ".previous.nbagm.zip")


def pending_restore_path(path: str | Path) -> Path:
    target = Path(path)
    return target.with_name(target.name + ".restore-pending.nbagm.zip")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_copy_file(path: Path, source: Path) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as reader:
                shutil.copyfileobj(reader, handle, COPY_CHUNK_BYTES)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_archive(path: Path, output: BinaryIO, *, local: bool = False, restore_snapshot_id: str | None = None,
                   loaded: dict | None = None) -> None:
    """``loaded``: the caller's own load_save of ``path``, read under the same lock (spares a second parse)."""
    from .history_store import history_sidecar_path
    from .save import load_save

    target = Path(path)
    expanded_limit = MAX_LOCAL_EXPANDED_BYTES if local else MAX_EXPANDED_BYTES
    archive_limit = MAX_LOCAL_ARCHIVE_BYTES if local else MAX_ARCHIVE_BYTES
    with save_lock(target), tempfile.TemporaryDirectory(prefix="nba-history-export-") as temporary:
        save = loaded if loaded is not None else load_save(target)
        members = {"save.json": target}
        if target.stat().st_size > MAX_MANIFEST_BYTES:
            raise SaveRecoveryError("The save manifest exceeds the recovery manifest size limit.")
        if save.get("history_store"):
            database = history_sidecar_path(target, save)
            snapshot = Path(temporary) / "history.sqlite3"
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(snapshot)) as destination:
                    source.backup(destination)
                    destination.execute("PRAGMA journal_mode=DELETE")
                    # A failed manifest publication may leave invisible future rows.
                    revision = save["history_store"]["revision"]
                    with destination:
                        destination.execute("DELETE FROM history_records WHERE revision > ?", (revision,))
                        if destination.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_commits'").fetchone():
                            destination.execute("DELETE FROM history_commits WHERE revision > ?", (revision,))
            # Only the history path differs from the save, and the copy is only serialized: a shallow copy with its
            # own history_store dict gives the same text as the deep copy did (MONTH-SPEED-2).
            checked = {**save, "history_store": {**save["history_store"], "path": snapshot.name}}
            staged_manifest = snapshot.parent / "save.json"
            staged_manifest.write_text(json.dumps(checked), encoding="utf-8")
            load_save(staged_manifest)
            members["history.sqlite3"] = snapshot
        if not local:
            # Finished seasons' archive files travel with a portable export. Local recovery archives leave them out:
            # they are written once and never change, and stay beside the save the backup restores.
            from .season_archive import archive_entries, archive_file_path
            for label, entry in sorted(archive_entries(save).items()):
                source = archive_file_path(target, entry)
                if source is None or not source.is_file():
                    raise SaveRecoveryError(f"The {label} season archive file is missing. Keep the save's files together.")
                members[season_archive_member(label)] = source
        descriptions = {}
        for name, member in members.items():
            with member.open("rb") as reader:
                checksum = hashlib.file_digest(reader, "sha256").hexdigest()
            descriptions[name] = {"sha256": checksum, "size": member.stat().st_size}
        metadata = {
            "format": BACKUP_FORMAT,
            "members": descriptions,
        }
        if restore_snapshot_id is not None:
            metadata["restore_snapshot_id"] = restore_snapshot_id
        encoded = json.dumps(metadata, sort_keys=True).encode("utf-8")
        if sum(row["size"] for row in descriptions.values()) + len(encoded) > expanded_limit:
            kind = "local recovery" if local else "portable export"
            raise SaveRecoveryError(f"This save exceeds the {kind} expanded size limit. Automatic local backups use a separate, larger limit.")
        # The automatic previous-save backup is rewritten on every save write; fast deflate (level 1) takes about
        # a third of the default's time for a ~40% larger file. Portable exports keep the default level.
        level = 1 if local else None
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level) as archive:
            for name, member in members.items():
                archive.write(member, name)
                if output.tell() > archive_limit:
                    raise SaveRecoveryError("This backup exceeds its compressed size limit.")
            archive.writestr("backup.json", encoded)
        if output.tell() > archive_limit:
            raise SaveRecoveryError("This backup exceeds its compressed size limit.")


def create_export(path: str | Path, *, _restore_snapshot_id: str | None = None) -> bytes:
    """Bounded portable upload/download; local autosaves never use this buffer."""
    output = io.BytesIO()
    _write_archive(Path(path), output, restore_snapshot_id=_restore_snapshot_id)
    return output.getvalue()


def _publish_local_archive(target: Path, archive: Path, *, restore_snapshot_id: str | None = None,
                           loaded: dict | None = None) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=archive.parent, prefix=f".{archive.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            _write_archive(target, handle, local=True, restore_snapshot_id=restore_snapshot_id, loaded=loaded)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(archive)
        fsync_directory(archive.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def preserve_previous_save(path: str | Path, loaded: dict | None = None) -> None:
    """Called under the writer's reentrant lock, before touching either component.

    ``loaded`` is the writer's load_save of the same file under that lock; it is only read here."""
    target = Path(path)
    if target.exists():
        _publish_local_archive(target, previous_backup_path(target), loaded=loaded)


def _extract_archive(source: Path | BinaryIO, directory: Path, *, local: bool = False) -> dict[str, Any]:
    """Validate inventory first, then hash/extract with bounded buffers and sizes."""
    archive_limit = MAX_LOCAL_ARCHIVE_BYTES if local else MAX_ARCHIVE_BYTES
    expanded_limit = MAX_LOCAL_EXPANDED_BYTES if local else MAX_EXPANDED_BYTES
    if isinstance(source, Path) and (source.is_symlink() or source.stat().st_size > archive_limit):
        raise SaveRecoveryError("The local recovery archive is unsafe or exceeds its size limit.")
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            allowed = {"backup.json", "save.json", "history.sqlite3"}
            if len(names) != len(set(names)) or not {"backup.json", "save.json"}.issubset(names) or {
                    name for name in set(names) - allowed if not SEASON_ARCHIVE_MEMBER.match(name)}:
                raise SaveRecoveryError("Invalid backup members or unsafe archive paths. Choose an exported NBA GM backup.")
            for entry in entries:
                mode = entry.external_attr >> 16
                if entry.orig_filename != entry.filename or entry.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG}) or entry.flag_bits & 1:
                    raise SaveRecoveryError("Backup contains an unsafe or encrypted archive entry.")
                if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise SaveRecoveryError("Unsupported backup compression.")
            expanded = sum(entry.file_size for entry in entries)
            if expanded > expanded_limit:
                raise SaveRecoveryError("Backup exceeds the expanded size limit.")
            if archive.getinfo("backup.json").file_size > MAX_METADATA_BYTES:
                raise SaveRecoveryError("Backup metadata exceeds its size limit.")
            if archive.getinfo("save.json").file_size > MAX_MANIFEST_BYTES:
                raise SaveRecoveryError("Backup manifest exceeds its size limit.")
            if expanded * 2 + 16 * 1024 * 1024 > shutil.disk_usage(directory).free:
                raise SaveRecoveryError("Not enough disk space to safely stage and restore this backup.")
            metadata = json.loads(archive.read("backup.json"))
            if not isinstance(metadata, dict) or metadata.get("format") != BACKUP_FORMAT:
                raise SaveRecoveryError("Unsupported backup format. Use a compatible NBA GM Sandbox version.")
            descriptions = metadata.get("members")
            if not isinstance(descriptions, dict) or set(descriptions) != set(names) - {"backup.json"}:
                raise SaveRecoveryError("Backup component inventory is incomplete.")
            for name, descriptor in descriptions.items():
                if (not isinstance(descriptor, dict) or type(descriptor.get("size")) is not int
                        or descriptor["size"] != archive.getinfo(name).file_size):
                    raise SaveRecoveryError(f"Backup inventory failed for {name}.")
                checksum, size = hashlib.sha256(), 0
                with archive.open(name) as reader, (directory / name).open("wb") as writer:
                    while chunk := reader.read(COPY_CHUNK_BYTES):
                        size += len(chunk)
                        if size > descriptor["size"]:
                            raise SaveRecoveryError(f"Backup exceeds its declared size for {name}.")
                        checksum.update(chunk)
                        writer.write(chunk)
                if size != descriptor["size"] or checksum.hexdigest() != descriptor.get("sha256"):
                    raise SaveRecoveryError(f"Backup checksum failed for {name}. Choose an intact backup.")
            return metadata
    except SaveRecoveryError:
        raise
    except (ValueError, OSError, RuntimeError, EOFError, zipfile.BadZipFile, NotImplementedError, zlib.error) as exc:
        raise SaveRecoveryError(f"Cannot read backup: {exc}. Choose an intact NBA GM backup.") from exc


@contextmanager
def _stage_archive(source: Path | BinaryIO, *, local: bool = False):
    with tempfile.TemporaryDirectory(prefix="nba-restore-check-") as temporary:
        directory = Path(temporary)
        metadata = _extract_archive(source, directory, local=local)
        yield directory, metadata


def finish_pending_restore(path: str | Path) -> bool:
    """Resolve a prior restore under save_lock; return whether it committed.

    Until manifest publication, the previous archive remains the recovery
    source. After publication, the staged outgoing snapshot becomes previous.
    Keep the pending archive through promotion errors, including a failure
    after replacement, so recovery retries finish rather than undo the restore.
    """
    from .save import load_save

    target = Path(path)
    pending = pending_restore_path(target)
    if not pending.is_file():
        return False
    with _stage_archive(pending, local=True) as (_, metadata):
        snapshot_id = metadata.get("restore_snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise SaveRecoveryError("The pending restore checkpoint is invalid. Keep the save and recovery files for troubleshooting.")
    # Fail closed if the current pair cannot be validated; retain both archives.
    current = load_save(target)
    committed = current.get("meta", {}).get("save_snapshot_id") == snapshot_id
    if committed:
        atomic_copy_file(previous_backup_path(target), pending)
    # Nothing fallible follows unlink: a failed promotion retains retry intent.
    # Cleanup need not be durable; a leftover intent is safe to resolve again.
    pending.unlink()
    return committed


def restore_export(path: str | Path, archive: bytes, *, replace: bool = False) -> dict[str, Any]:
    if not isinstance(archive, bytes) or len(archive) > MAX_ARCHIVE_BYTES:
        raise SaveRecoveryError("Choose a valid NBA GM backup smaller than 128 MB.")
    with _stage_archive(io.BytesIO(archive)) as (directory, _):
        return _restore_staged(Path(path), directory, replace=replace)


def _restore_staged(target: Path, directory: Path, *, replace: bool) -> dict[str, Any]:
    from .history_store import SaveValidationError, history_sidecar_path
    from .save import load_save

    # Parse and validate in isolation before even creating the destination directory.
    try:
        manifest = json.loads((directory / "save.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise SaveRecoveryError("Backup save manifest must be a JSON object.")
        store = manifest.get("history_store")
        if bool(store) != (directory / "history.sqlite3").is_file():
            raise SaveRecoveryError("Backup is missing a required history component or contains unexpected history.")
        if store and not isinstance(store, dict):
            raise SaveRecoveryError("Backup history descriptor is invalid.")
        # Validate the original path before replacing it with our fixed staging name.
        if store:
            history_sidecar_path(Path("save.json"), manifest)
        staged = directory / "save.json"
        if store:
            store["path"] = "history.sqlite3"
        staged.write_text(json.dumps(manifest), encoding="utf-8")
        load_save(staged)
    except (SaveRecoveryError, SaveValidationError):
        raise
    except (ValueError, TypeError, OSError, sqlite3.Error) as exc:
        raise SaveRecoveryError(f"Backup validation failed: {exc}") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    with save_lock(target):
        finish_pending_restore(target)
        manifest.setdefault("meta", {})["save_snapshot_id"] = uuid.uuid4().hex
        if not replace:
            ensure_new_save_path(target)
        elif target.exists():
            try:
                load_save(target)
            except SaveValidationError:
                # Keep unreadable evidence as well as the last good recovery archive.
                damaged = target.with_name(f"{target.name}.unreadable-{uuid.uuid4().hex}.bak")
                atomic_write_bytes(damaged, target.read_bytes())
            else:
                # Do not overwrite the recovery source before the manifest
                # commits. The staged archive is also the durable retry intent.
                _publish_local_archive(target, pending_restore_path(target),
                                       restore_snapshot_id=manifest["meta"]["save_snapshot_id"])
        if store:
            store["path"] = f"{target.stem}.restored-{uuid.uuid4().hex}.history.sqlite3"
            atomic_copy_file(target.parent / store["path"], directory / "history.sqlite3")
        _restore_season_archives(target, directory, manifest)
        # The old manifest and its database are untouched until this single switch.
        atomic_write_bytes(target, (json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8"))
        finish_pending_restore(target)
    return {"status": "restored", "save_path": str(target)}


def _restore_season_archives(target: Path, directory: Path, manifest: dict[str, Any]) -> None:
    """Put an export's season archive files beside the restored save under its name. A local recovery archive
    carries none: the files it references are still beside the save."""
    from .season_archive import archive_entries

    for label, entry in archive_entries(manifest).items():
        staged = directory / season_archive_member(label)
        if not staged.is_file():
            continue
        with staged.open("rb") as reader:
            digest = hashlib.file_digest(reader, "sha256").hexdigest()
        if digest != entry.get("sha256"):
            raise SaveRecoveryError(f"The {label} season archive in this backup does not match its save.")
        entry["file"] = f"{target.stem}.season-{label}.{digest[:12]}.json.gz"
        atomic_copy_file(target.parent / entry["file"], staged)


def recover_previous_save(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    with save_lock(target):
        if finish_pending_restore(target):
            # Manifest publication already completed in the interrupted call.
            return {"status": "restored", "save_path": str(target)}
        backup = previous_backup_path(target)
        if not backup.is_file():
            raise SaveRecoveryError("No previous backup is available. Restore an exported NBA GM backup instead.")
        with _stage_archive(backup, local=True) as (directory, _):
            return _restore_staged(target, directory, replace=True)


def ensure_new_save_path(path: str | Path) -> None:
    target = Path(path)
    # A manifest lost in an interruption must not cause old history to be adopted.
    if target.exists() or target.is_symlink() or target.with_suffix(".history.sqlite3").exists() or previous_backup_path(target).exists() or pending_restore_path(target).exists() or any(target.parent.glob(f"{target.stem}.*.history.sqlite3")) or any(target.parent.glob(f"{target.stem}.season-*.json.gz")):
        raise SaveRecoveryError(f"A save or recovery data named '{target.stem}' already exists. Choose a different save name or recover the existing save.")

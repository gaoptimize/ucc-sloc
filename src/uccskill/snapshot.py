"""Timestamped JSON snapshots under a history directory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from uccskill.crawl import FileRecord

SNAPSHOT_VERSION = 2


def snapshot_document(
    files: list[FileRecord],
    *,
    root: str,
    label: str = "",
    git_ref: str | None = None,
    snapshot_id: str | None = None,
    created: datetime | None = None,
) -> dict:
    created = created or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    stamp = snapshot_id or created.strftime("%Y%m%dT%H%M%SZ")
    return {
        "version": SNAPSHOT_VERSION,
        "id": stamp,
        "created": created.isoformat(),
        "root": root,
        "label": label,
        "git_ref": git_ref,
        "files": [record.to_json() for record in files],
    }


def save_snapshot(
    history: Path,
    files: list[FileRecord],
    *,
    root: str,
    label: str = "",
    git_ref: str | None = None,
) -> Path:
    history.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc)
    stamp = created.strftime("%Y%m%dT%H%M%S%fZ")
    path = history / f"{stamp}.json"
    suffix = 1
    while path.exists():
        suffix += 1
        path = history / f"{stamp}_{suffix}.json"
    payload = snapshot_document(
        files,
        root=root,
        label=label,
        git_ref=git_ref,
        snapshot_id=path.stem,
        created=created,
    )
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_snapshots(history: Path) -> list[dict]:
    if not history.is_dir():
        return []
    loaded = []
    for path in sorted(history.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "files" not in data:
            continue
        data["id"] = path.stem
        data["files"] = [FileRecord.from_json(item) for item in data["files"]]
        loaded.append(data)
    loaded.sort(key=lambda item: (item.get("created") or "", item["id"]))
    return loaded


def find_snapshot(snapshots: list[dict], snapshot_id: str | None) -> dict | None:
    if not snapshots:
        return None
    if snapshot_id:
        for item in snapshots:
            if item["id"] == snapshot_id:
                return item
        return None
    return snapshots[-1]

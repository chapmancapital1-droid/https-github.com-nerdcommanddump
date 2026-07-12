"""
Brain knowledge versioning — snapshot, list, rollback.

Every meaningful change to the brain (parameter tune, agent promotion,
retrain) can be checkpointed as an immutable snapshot on disk:

  versions/
    v2.1.0-20260711-163000.json    ← full brain-state dump + label + notes
    v2.1.1-20260712-090000.json
    index.json                     ← ordered catalog of all snapshots

Rollback = load any older snapshot back into a live brain. The index keeps
lineage (`parent`) so the dashboard's version tab can render the history
as a chain.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class BrainVersionStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        if not self.index_path.exists():
            self._write_index([])

    # -- index ----------------------------------------------------------------

    def _read_index(self) -> list[dict[str, Any]]:
        return json.loads(self.index_path.read_text())

    def _write_index(self, entries: list[dict[str, Any]]) -> None:
        self.index_path.write_text(json.dumps(entries, indent=2))

    def list_versions(self) -> list[dict[str, Any]]:
        """Catalog entries, oldest first: id, label, notes, created, parent."""
        return self._read_index()

    def latest(self) -> dict[str, Any] | None:
        entries = self._read_index()
        return entries[-1] if entries else None

    # -- snapshot / rollback -----------------------------------------------------

    def snapshot(
        self,
        brain_state: dict[str, Any],
        label: str,
        notes: str = "",
    ) -> str:
        """Persist a full brain-state dump; returns the new version id."""
        entries = self._read_index()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        version_id = f"{label}-{stamp}"
        # Same label within the same second must not overwrite the earlier
        # snapshot or duplicate an index id — disambiguate with a counter.
        existing_ids = {e["id"] for e in entries}
        if version_id in existing_ids:
            n = 2
            while f"{version_id}-{n}" in existing_ids:
                n += 1
            version_id = f"{version_id}-{n}"
        parent = entries[-1]["id"] if entries else None

        payload = {
            "id": version_id,
            "label": label,
            "notes": notes,
            "parent": parent,
            "created_at": time.time(),
            "state": brain_state,
        }
        (self.root / f"{version_id}.json").write_text(
            json.dumps(payload, indent=2)
        )
        entries.append(
            {
                "id": version_id,
                "label": label,
                "notes": notes,
                "parent": parent,
                "created_at": payload["created_at"],
            }
        )
        self._write_index(entries)
        return version_id

    def load(self, version_id: str) -> dict[str, Any]:
        """Return the full brain-state dict stored under a version id."""
        path = self.root / f"{version_id}.json"
        if not path.exists():
            raise KeyError(f"unknown brain version: {version_id}")
        return json.loads(path.read_text())["state"]

    def rollback(self, version_id: str, reason: str = "") -> dict[str, Any]:
        """
        Load an older state AND record the rollback itself as a new snapshot,
        so history is append-only (you can roll back a rollback).
        """
        state = self.load(version_id)
        self.snapshot(
            state,
            label=f"rollback-to-{version_id}",
            notes=reason or f"rolled back to {version_id}",
        )
        return state

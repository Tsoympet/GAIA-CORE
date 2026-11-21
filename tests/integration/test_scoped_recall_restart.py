"""A second process must rank a scoped note from the same SQLite file."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gaia.memory import MemoryManager, MemoryScope
from gaia.memory.indexer import SCORES_CALIBRATED, SQLITE_VECTOR_INDEX
from gaia.memory.sqlite_index import SQLiteVectorIndex

NOTE = "Pump curve at 50 hertz stays on disk"
RELATED = "Spare pump seals in the workshop drawer"
UNRELATED = "Kitchen inventory for spare bolts"
OTHER_OWNER = "Pump curve for the other owner"

_CHILD = """
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from gaia.server.app import create_app

db_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
client = TestClient(create_app(phase4_db=db_path))
recalled = client.post(
    "/memory/recall",
    json={"query": "pump curve", "owner_id": "local", "limit": 5},
)
status = client.get("/memory/status").json()
hits = recalled.json()
payload = {
    "pid": os.getpid(),
    "status_code": recalled.status_code,
    "hits": [
        {
            "rank": index,
            "record_id": hit["record_id"],
            "content": hit["content"],
            "score": hit["score"],
            "score_calibrated": hit["score_calibrated"],
        }
        for index, hit in enumerate(hits)
    ],
    "durable": status["durable"],
    "scores_calibrated": status["scores_calibrated"],
    "vector_index": status["vector_index"],
    "score_note": status["score_note"],
}
out_path.write_text(json.dumps(payload), encoding="utf-8")
"""


def test_scoped_recall_rank_survives_a_new_process(tmp_path: Path) -> None:
    db_path = tmp_path / "phase4.sqlite3"
    memory = MemoryManager(vector_store=SQLiteVectorIndex(db_path))
    kept = memory.remember(NOTE, MemoryScope.PROJECT, "local")
    memory.remember(RELATED, MemoryScope.SESSION, "local")
    memory.remember(UNRELATED, MemoryScope.USER, "local")
    memory.remember(OTHER_OWNER, MemoryScope.PROJECT, "other")
    matches = memory.recall("pump curve", "local")
    assert [record.content for record, _score in matches][0] == NOTE
    assert matches[0][0].record_id == kept.record_id
    parent_ids = [record.record_id for record, _score in matches]
    parent_scores = [score for _record, score in matches]
    parent_rank = parent_ids.index(kept.record_id)
    assert memory.status().durable is True
    assert memory.status().scores_calibrated is False
    assert isinstance(memory.vector_store, SQLiteVectorIndex)
    memory.vector_store.close()

    out_path = tmp_path / "recall.json"
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD, str(db_path), str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["pid"] != os.getpid()
    assert payload["status_code"] == 200
    hits = payload["hits"]
    assert [hit["record_id"] for hit in hits] == parent_ids
    assert [hit["rank"] for hit in hits] == list(range(len(parent_ids)))
    winner = hits[parent_rank]
    assert winner["content"] == NOTE
    assert winner["rank"] == parent_rank
    assert winner["score"] == pytest.approx(parent_scores[parent_rank])
    assert winner["score_calibrated"] is False
    assert winner["score_calibrated"] is SCORES_CALIBRATED
    assert all(hit["score_calibrated"] is False for hit in hits)
    assert OTHER_OWNER not in [hit["content"] for hit in hits]
    assert payload["durable"] is True
    assert payload["scores_calibrated"] is False
    assert payload["vector_index"] == SQLITE_VECTOR_INDEX
    assert "uncalibrated" in payload["score_note"]

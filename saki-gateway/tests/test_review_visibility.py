from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from saki_gateway.memory import MemoryStore
from saki_gateway.server import GatewayApp


class ReviewVisibilityTests(unittest.TestCase):
    def _make_store(self) -> MemoryStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "memories.db"
        return MemoryStore(db_path)

    def _make_app(self) -> GatewayApp:
        app = GatewayApp.__new__(GatewayApp)
        app.memory_store = self._make_store()
        app.runtime_store = SimpleNamespace(list_events=lambda limit=50: [])
        app._events = []
        app.record_event = lambda event_type, payload: app._events.append((event_type, payload))
        app._write_text_file = lambda _path, _content: None
        app._core_memory_file = lambda: Path("/tmp/core_profile.md")
        app._active_memory_file = lambda: Path("/tmp/active_memory.md")
        app._read_text_file = lambda path: ""
        app._now_in_local_timezone = lambda: __import__("datetime").datetime(2026, 1, 2, 9, 0, 0)
        app.config_store = SimpleNamespace(
            config=SimpleNamespace(
                persona=SimpleNamespace(
                    partner_name="Aelios",
                    partner_role="AI 伴侣",
                    call_user="你",
                    core_identity="温柔",
                    boundaries="不生硬",
                )
            )
        )
        app.list_memories_grouped = lambda: {"items": []}
        return app

    def _seed_proposal(self, app: GatewayApp, content: str) -> str:
        result = app._create_core_update_proposal(
            target_section="My Profile",
            proposed_content=content,
            reason="digest",
            source_context="ctx",
            proposal_type="preference",
            confidence="high",
        )
        return result["proposal_id"]

    def test_listing_open_proposals_default(self) -> None:
        app = self._make_app()
        proposal_id = self._seed_proposal(app, "喜欢周末徒步")

        payload = app.list_core_update_proposals()

        self.assertEqual(payload["status"], "open")
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["id"], proposal_id)
        self.assertEqual(item["status"], "open")
        for key in [
            "target_section",
            "proposed_content",
            "proposal_type",
            "confidence",
            "reason",
            "source_context",
            "created_at",
            "updated_at",
            "reviewed_at",
        ]:
            self.assertIn(key, item)

    def test_listing_open_proposals_newest_first(self) -> None:
        app = self._make_app()
        first_id = self._seed_proposal(app, "喜欢晨跑")
        second_id = self._seed_proposal(app, "喜欢夜间散步")

        payload = app.list_core_update_proposals(status="open")

        self.assertEqual(payload["items"][0]["id"], second_id)
        self.assertEqual(payload["items"][1]["id"], first_id)

    def test_approve_operation_returns_updated_status(self) -> None:
        app = self._make_app()
        proposal_id = self._seed_proposal(app, "偏好: 晚饭后散步")

        payload = app.approve_core_update_proposal(proposal_id)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["proposal"]["status"], "approved")
        self.assertTrue(payload["proposal"]["reviewed_at"])

    def test_reject_operation_returns_updated_status(self) -> None:
        app = self._make_app()
        proposal_id = self._seed_proposal(app, "偏好: 睡前听歌")

        payload = app.reject_core_update_proposal(proposal_id)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["proposal"]["status"], "rejected")
        self.assertTrue(payload["proposal"]["reviewed_at"])

    def test_digest_run_state_visibility_payload(self) -> None:
        app = self._make_app()
        app._read_digest_run_state = lambda: {
            "id": "2026-01-02",
            "run_state": "nightly_digest",
            "status": "success",
            "started_at": "2026-01-02T04:05:00+08:00",
            "completed_at": "2026-01-02T04:05:11+08:00",
            "error_message": "",
        }
        app.runtime_store = SimpleNamespace(
            list_events=lambda limit=50: [
                {
                    "event_type": "digest_run",
                    "payload": {
                        "id": "2026-01-01",
                        "run_state": "nightly_digest",
                        "status": "failed",
                        "started_at": "2026-01-01T04:05:00+08:00",
                        "completed_at": "2026-01-01T04:05:03+08:00",
                        "error_message": "down",
                    },
                    "created_at": "2026-01-01T04:05:03+08:00",
                }
            ]
        )

        payload = app.digest_run_state_payload()

        self.assertEqual(payload["local_date"], "2026-01-02")
        self.assertTrue(payload["completed_successfully_for_current_local_date"])
        self.assertEqual(payload["latest"]["status"], "success")
        self.assertEqual(payload["history"][0]["status"], "failed")

    def test_memory_inspection_output(self) -> None:
        app = self._make_app()
        app._read_text_file = lambda path: (
            "# header\n## About Her\n- 温柔\n## Relationship Core\n- 认真沟通\n## My Profile\n- 喜欢徒步\n"
            if "core_profile" in str(path)
            else "# header\n## Current Status\n- 最近忙\n## Purpose Context\n- 稳定陪伴\n## On the Horizon\n- 周末约会\n## Others\n- 记录中\n"
        )

        payload = app.memory_inspection_payload()

        self.assertIn("About Her", payload["core_profile"]["sections"])
        self.assertIn("Relationship Core", payload["core_profile"]["sections"])
        self.assertIn("My Profile", payload["core_profile"]["sections"])
        self.assertIn("Current Status", payload["active_memory"]["sections"])
        self.assertIn("Purpose Context", payload["active_memory"]["sections"])
        self.assertIn("On the Horizon", payload["active_memory"]["sections"])
        self.assertIn("Others", payload["active_memory"]["sections"])


if __name__ == "__main__":
    unittest.main()

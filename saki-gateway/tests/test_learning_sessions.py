from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from saki_gateway.runtime_store import RuntimeStore
from saki_gateway.server import GatewayApp


class LearningSessionTests(unittest.TestCase):
    def _make_runtime_store(self) -> RuntimeStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        return RuntimeStore(base / "gateway.db", base / "events.jsonl")

    def _make_app(self) -> GatewayApp:
        app = GatewayApp.__new__(GatewayApp)
        app.runtime_store = self._make_runtime_store()
        app.memory_store = SimpleNamespace(upsert_memory=lambda **kwargs: None)
        app._refresh_active_memory = lambda: None
        app._events = []
        app._record_event = lambda event_type, payload, **kwargs: app._events.append((event_type, payload))
        return app

    def _start(self, app: GatewayApp, **overrides):
        body = {
            "title": "线代复习",
            "goal": "先做两道题",
            "subject": "线性代数",
            "mode": "focus",
            "planned_minutes": 15,
            "pomodoro_count": 1,
            "started_at": "2026-01-02T10:00:00",
        }
        body.update(overrides)
        return app.create_learning_session_payload(body)["item"]

    def test_creating_learning_session(self) -> None:
        app = self._make_app()
        item = self._start(app)
        self.assertEqual(item["status"], "active")
        self.assertEqual(item["planned_minutes"], 15)

    def test_prevent_multiple_active_sessions(self) -> None:
        app = self._make_app()
        self._start(app)
        with self.assertRaises(ValueError):
            self._start(app, title="第二个会话")

    def test_update_active_session(self) -> None:
        app = self._make_app()
        item = self._start(app)
        updated = app.update_learning_session_payload(
            item["id"], {"planned_minutes": 5, "mode": "recovery", "goal": "低负担继续"}
        )["item"]
        self.assertEqual(updated["planned_minutes"], 5)
        self.assertEqual(updated["mode"], "recovery")

    def test_complete_learning_session(self) -> None:
        app = self._make_app()
        item = self._start(app)
        completed = app.complete_learning_session_payload(
            item["id"],
            {
                "ended_at": "2026-01-02T10:27:00",
                "summary": "完成两道基础题",
                "blockers": "第二题计算慢",
                "next_step": "晚点复盘错题",
            },
        )["item"]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["actual_minutes"], 27)

    def test_abandon_learning_session(self) -> None:
        app = self._make_app()
        item = self._start(app)
        abandoned = app.abandon_learning_session_payload(
            item["id"],
            {
                "ended_at": "2026-01-02T10:08:00",
                "summary": "状态不佳，先缓一缓",
                "next_step": "午休后做10分钟",
            },
        )["item"]
        self.assertEqual(abandoned["status"], "abandoned")

    def test_invalid_state_transition_rejected(self) -> None:
        app = self._make_app()
        item = self._start(app)
        app.complete_learning_session_payload(item["id"], {"ended_at": "2026-01-02T10:27:00"})
        with self.assertRaises(ValueError):
            app.abandon_learning_session_payload(item["id"], {})

    def test_actual_minutes_calculation(self) -> None:
        app = self._make_app()
        item = self._start(app, started_at="2026-01-02T09:00:00")
        completed = app.complete_learning_session_payload(
            item["id"], {"ended_at": "2026-01-02T09:42:00"}
        )["item"]
        self.assertEqual(completed["actual_minutes"], 42)

    def test_create_start_and_end_checkins(self) -> None:
        app = self._make_app()
        created = app.create_learning_session_payload(
            {
                "title": "英语复习",
                "goal": "复习20个单词",
                "mode": "recovery",
                "planned_minutes": 10,
                "start_checkin": {"energy_level": 2, "mood_level": 3, "note": "有点累"},
            }
        )["item"]
        app.complete_learning_session_payload(
            created["id"],
            {
                "ended_at": "2026-01-02T11:10:00",
                "end_checkin": {"focus_level": 3, "stress_level": 2, "note": "比预期好"},
            },
        )
        checkins = app.list_wellbeing_checkins_payload(created["id"])["items"]
        self.assertEqual(len(checkins), 2)
        stages = {item["stage"] for item in checkins}
        self.assertEqual(stages, {"start", "end"})

    def test_list_current_active_session(self) -> None:
        app = self._make_app()
        created = self._start(app)
        active = app.get_active_learning_session_payload()["item"]
        self.assertEqual(active["id"], created["id"])

    def test_list_recent_sessions(self) -> None:
        app = self._make_app()
        first = self._start(app, title="会话A")
        app.complete_learning_session_payload(first["id"], {"ended_at": "2026-01-02T10:20:00"})
        second = self._start(app, title="会话B")
        app.abandon_learning_session_payload(second["id"], {"ended_at": "2026-01-02T11:15:00"})
        listed = app.list_learning_sessions_payload(limit=5)["items"]
        self.assertEqual(len(listed), 2)
        self.assertIn(listed[0]["status"], {"completed", "abandoned"})

    def test_retrieve_associated_checkins(self) -> None:
        app = self._make_app()
        created = self._start(app)
        app.add_wellbeing_checkin_payload(created["id"], {"stage": "start", "focus_level": 3})
        app.add_wellbeing_checkin_payload(created["id"], {"stage": "end", "note": "今天到这里"})
        payload = app.list_wellbeing_checkins_payload(created["id"])
        self.assertEqual(payload["session_id"], created["id"])
        self.assertEqual(len(payload["items"]), 2)


if __name__ == "__main__":
    unittest.main()

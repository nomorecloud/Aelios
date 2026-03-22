from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from saki_gateway.config import AppConfig, PersonaConfig
from saki_gateway.runtime_store import RuntimeStore
from saki_gateway.server import GatewayApp
from saki_gateway.study_companion import StudyCompanionResponder, StudyPersonaLayers
from saki_gateway.study_progress import StudyProgressSummarizer


class LearningSessionTests(unittest.TestCase):
    def _make_runtime_store(self) -> RuntimeStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        return RuntimeStore(base / "gateway.db", base / "events.jsonl")

    def _make_app(self) -> GatewayApp:
        app = GatewayApp.__new__(GatewayApp)
        app.runtime_store = self._make_runtime_store()
        app.config_store = SimpleNamespace(
            config=AppConfig(
                persona=PersonaConfig(
                    partner_name="Aelios",
                    partner_role="AI companion",
                    call_user="你",
                    base_persona="冷静、专注、会稳稳接住用户。",
                    study_overlay="学习时用短句、明确动作、不给羞辱压力。",
                    recovery_overlay="恢复时先安抚和减压，再决定是否继续。",
                    safety_notes="禁止露骨亲密、羞辱、惩罚或胁迫。",
                )
            )
        )
        app.memory_store = SimpleNamespace(upsert_memory=lambda **kwargs: None)
        app._refresh_active_memory = lambda: None
        app._events = []
        app._record_event = lambda event_type, payload, **kwargs: app._events.append((event_type, payload))
        app.study_responder = StudyCompanionResponder()
        app.study_progress = StudyProgressSummarizer()
        app.scheduler = SimpleNamespace(stop=lambda: None, start=lambda: None, status=lambda: {})
        app.feishu_channel = None
        app.qqbot_channel = None
        app.napcat_channel = None
        app.tools = SimpleNamespace(list_enabled=lambda: [])
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
        self.assertEqual(item["runtime_state"], "focus")
        events = app.list_learning_session_events_payload(item["id"])["items"]
        self.assertEqual(events[0]["event_type"], "session_started")

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

    def test_pause_and_resume_runtime_events(self) -> None:
        app = self._make_app()
        item = self._start(app)
        paused = app.update_learning_session_runtime_payload(
            item["id"],
            {"action": "pause", "timestamp": "2026-01-02T10:05:00", "elapsed_minutes": 5, "remaining_minutes": 10},
        )["item"]
        self.assertEqual(paused["runtime_state"], "paused")
        resumed = app.update_learning_session_runtime_payload(
            item["id"],
            {"action": "resume", "timestamp": "2026-01-02T10:08:00", "elapsed_minutes": 5, "remaining_minutes": 10},
        )["item"]
        self.assertEqual(resumed["runtime_state"], "focus")
        event_types = [event["event_type"] for event in app.list_learning_session_events_payload(item["id"])["items"]]
        self.assertIn("session_paused", event_types)
        self.assertIn("session_resumed", event_types)

    def test_focus_and_break_events(self) -> None:
        app = self._make_app()
        item = self._start(app)
        app.update_learning_session_runtime_payload(item["id"], {"action": "focus_completed", "elapsed_minutes": 15, "remaining_minutes": 0})
        on_break = app.update_learning_session_runtime_payload(item["id"], {"action": "break_started", "elapsed_minutes": 15, "remaining_minutes": 5})["item"]
        self.assertEqual(on_break["runtime_state"], "break")
        back = app.update_learning_session_runtime_payload(item["id"], {"action": "break_completed", "elapsed_minutes": 15, "remaining_minutes": 5})["item"]
        self.assertEqual(back["runtime_state"], "focus")
        event_types = [event["event_type"] for event in app.list_learning_session_events_payload(item["id"])["items"]]
        self.assertIn("focus_completed", event_types)
        self.assertIn("break_completed", event_types)

    def test_runtime_transition_validation_rejects_out_of_order_actions(self) -> None:
        app = self._make_app()
        item = self._start(app)
        with self.assertRaises(ValueError):
            app.update_learning_session_runtime_payload(item["id"], {"action": "break_started"})
        app.update_learning_session_runtime_payload(item["id"], {"action": "focus_completed", "elapsed_minutes": 15, "remaining_minutes": 0})
        with self.assertRaises(ValueError):
            app.update_learning_session_runtime_payload(item["id"], {"action": "resume"})

    def test_runtime_event_payload_includes_state_transition_metadata(self) -> None:
        app = self._make_app()
        item = self._start(app)
        app.update_learning_session_runtime_payload(item["id"], {"action": "focus_completed", "elapsed_minutes": 15, "remaining_minutes": 0})
        event = app.list_learning_session_events_payload(item["id"])["items"][0]
        self.assertEqual(event["event_type"], "focus_completed")
        self.assertEqual(event["payload"]["from_state"], "focus")
        self.assertEqual(event["payload"]["to_state"], "focus_completed")
        response = app.list_learning_session_responses_payload(item["id"])["items"][0]
        self.assertEqual(response["response_context"]["event_type"], "focus_completed")

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

    def test_low_energy_start_generates_event(self) -> None:
        app = self._make_app()
        created = app.create_learning_session_payload(
            {
                "title": "英语复习",
                "goal": "复习20个单词",
                "mode": "recovery",
                "planned_minutes": 10,
                "start_checkin": {"energy_level": 1, "stress_level": 4, "note": "有点累，快撑不住"},
            }
        )["item"]
        event_types = [event["event_type"] for event in app.list_learning_session_events_payload(created["id"])["items"]]
        self.assertIn("low_energy_start", event_types)

    def test_low_energy_start_response_prefers_stabilization(self) -> None:
        app = self._make_app()
        created = app.create_learning_session_payload(
            {
                "title": "英语复习",
                "goal": "复习20个单词",
                "mode": "recovery",
                "planned_minutes": 10,
                "start_checkin": {"energy_level": 1, "stress_level": 5, "note": "焦虑，快撑不住了"},
            }
        )["item"]
        responses = app.list_learning_session_responses_payload(created["id"])["items"]
        low_energy = next(resp for resp in responses if resp["event_type"] == "low_energy_start")
        self.assertIn("最小", low_energy["message"])
        self.assertTrue(low_energy["response_context"]["wellbeing_signal"]["overwhelmed"])
        self.assertIn(low_energy["response_context"]["recovery_state"]["state"], {"low_energy", "recovery_needed"})
        self.assertEqual(low_energy["response_context"]["style_effects"]["correction_tone"], "gentle_redirect")

    def test_style_config_affects_response_selection(self) -> None:
        app = self._make_app()
        item = self._start(app)
        app.update_learning_response_style_payload({"dominance_style": "high", "correction_style": "firm"}, session_id=item["id"])
        app.update_learning_session_runtime_payload(item["id"], {"action": "pause", "elapsed_minutes": 6, "remaining_minutes": 9})
        app.update_learning_session_runtime_payload(item["id"], {"action": "paused_too_long"})
        responses = app.list_learning_session_responses_payload(item["id"])["items"]
        paused_too_long = next(resp for resp in responses if resp["event_type"] == "session_paused_too_long")
        self.assertTrue(any(fragment in paused_too_long["message"] for fragment in ["不要继续往后拖", "别再让停顿继续扩大", "别把重启这件事一直往后放"]))

    def test_firm_vs_caring_response_behavior(self) -> None:
        app = self._make_app()
        firm = self._start(app, title="高强度")
        app.update_learning_response_style_payload({"dominance_style": "high", "correction_style": "firm"}, session_id=firm["id"])
        app.update_learning_session_runtime_payload(firm["id"], {"action": "pause", "elapsed_minutes": 7, "remaining_minutes": 8})
        app.update_learning_session_runtime_payload(firm["id"], {"action": "paused_too_long"})
        firm_message = next(resp["message"] for resp in app.list_learning_session_responses_payload(firm["id"])["items"] if resp["event_type"] == "session_paused_too_long")

        app.complete_learning_session_payload(firm["id"], {"ended_at": "2026-01-02T10:15:00"})
        caring = self._start(app, title="低能量", start_checkin={"energy_level": 1, "stress_level": 5, "note": "好累"})
        app.update_learning_session_runtime_payload(caring["id"], {"action": "pause", "elapsed_minutes": 2, "remaining_minutes": 13})
        app.update_learning_session_runtime_payload(caring["id"], {"action": "paused_too_long"})
        caring_message = next(resp["message"] for resp in app.list_learning_session_responses_payload(caring["id"])["items"] if resp["event_type"] == "session_paused_too_long")
        self.assertNotEqual(firm_message, caring_message)
        self.assertTrue(any(fragment in caring_message for fragment in ["体面收尾", "目标降到更小", "直接好好收尾"]))


    def test_anxious_state_adapts_response_behavior(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="session_resumed",
            session={"mode": "focus", "goal": "做两道题"},
            style=responder.normalize_style({"dominance_style": "high", "correction_style": "firm"}),
            wellbeing={"stress_level": 5, "note": "很焦虑，心里发紧"},
            recent_events=[{"event_type": "session_paused_too_long"}],
        )
        self.assertEqual(plan.debug["recovery_state"]["state"], "anxious_or_stressed")
        self.assertEqual(plan.debug["adaptation"]["pressure_level"], "softened")
        self.assertIn("不需要补偿式猛冲", plan.message)

    def test_smaller_next_step_selection_under_strain(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="session_paused_too_long",
            session={"mode": "review", "goal": "整理错题"},
            style=responder.normalize_style(None),
            wellbeing={"energy_level": 2, "stress_level": 4, "note": "有点乱"},
            recent_events=[
                {"event_type": "session_paused_too_long"},
                {"event_type": "session_paused"},
                {"event_type": "session_paused"},
            ],
        )
        self.assertIn(plan.debug["next_step"]["category"], {"take_short_break", "do_one_tiny_next_action"})
        self.assertNotEqual(plan.debug["next_step"]["category"], "continue_current_block")

    def test_stable_vs_recovery_needed_tone_differs(self) -> None:
        responder = StudyCompanionResponder()
        style = responder.normalize_style({"dominance_style": "high", "correction_style": "firm"})
        stable = responder.build_response_plan(
            event_type="session_paused_too_long",
            session={"mode": "focus", "goal": "做两道题"},
            style=style,
            recent_events=[],
        )
        fragile = responder.build_response_plan(
            event_type="session_paused_too_long",
            session={"mode": "focus", "goal": "做两道题", "summary": "太累了先休息"},
            style=style,
            wellbeing={"body_state_level": 1, "note": "头痛，想休息"},
            recent_events=[{"event_type": "session_paused_too_long"}, {"event_type": "session_paused_too_long"}],
        )
        self.assertEqual(stable.debug["adaptation"]["pressure_level"], "firm")
        self.assertEqual(fragile.debug["adaptation"]["pressure_level"], "recovery_first")
        self.assertIn("先休息", fragile.message)
        self.assertNotEqual(stable.message, fragile.message)

    def test_recovery_logic_overrides_harsher_style_tendencies(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="session_paused_too_long",
            session={"mode": "focus", "goal": "做两道题"},
            style=responder.normalize_style({"dominance_style": "high", "correction_style": "firm", "praise_style": "possessive_lite"}),
            wellbeing={"energy_level": 1, "stress_level": 5, "note": "焦虑又很累"},
            recent_events=[{"event_type": "session_paused_too_long"}],
        )
        self.assertEqual(plan.debug["style_effects"]["pressure_override"], "softened_for_recovery")
        self.assertEqual(plan.debug["style_effects"]["correction_tone"], "gentle_redirect")
        self.assertNotIn("不要继续往后拖", plan.message)

    def test_framework_inspection_includes_recovery_and_adaptation_visibility(self) -> None:
        app = self._make_app()
        created = self._start(app, start_checkin={"energy_level": 1, "stress_level": 4, "note": "太累了"})
        framework = app.get_learning_response_framework_payload(created["id"])["framework"]
        self.assertIn("recovery_state", framework)
        self.assertIn("derived_recovery_state", framework["inspection"])
        self.assertIn("recent_adapted_behaviors", framework["inspection"])
        self.assertGreaterEqual(len(framework["inspection"]["recent_adapted_behaviors"]), 1)

    def test_fragile_state_safety_avoids_guilt_or_intimate_language(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="session_abandoned",
            session={"mode": "focus", "goal": "做两道题"},
            style=responder.normalize_style({"dominance_style": "high", "praise_style": "possessive_lite"}),
            wellbeing={"body_state_level": 1, "note": "难受，先休息"},
            recent_events=[{"event_type": "session_paused_too_long"}, {"event_type": "session_abandoned"}],
        )
        lowered = plan.message.lower()
        for fragment in ["应该", "羞", "乖乖", "惩罚"]:
            self.assertNotIn(fragment, lowered)
        self.assertIn("先恢复", plan.message)

    def test_repeated_event_responses_rotate_variants(self) -> None:
        responder = StudyCompanionResponder()
        style = responder.normalize_style(None)
        first = responder.build_response_plan(
            event_type="session_paused_too_long",
            session={"mode": "focus", "goal": "做两道题"},
            style=style,
            recent_events=[],
        )
        second = responder.build_response_plan(
            event_type="session_paused_too_long",
            session={"mode": "focus", "goal": "做两道题"},
            style=style,
            recent_events=[{"event_type": "session_paused_too_long"}],
        )
        self.assertNotEqual(first.message, second.message)
        self.assertEqual(second.debug["response_selection"]["selected_index"], 1)

    def test_safety_constraint_no_degrading_output(self) -> None:
        app = self._make_app()
        item = self._start(app)
        app.update_learning_response_style_payload({"dominance_style": "high", "praise_style": "possessive_lite"}, session_id=item["id"])
        app.complete_learning_session_payload(item["id"], {"ended_at": "2026-01-02T10:20:00"})
        for response in app.list_learning_session_responses_payload(item["id"])["items"]:
            lowered = response["message"].lower()
            for banned in ["punish", "worthless", "idiot", "stupid", "humiliate"]:
                self.assertNotIn(banned, lowered)

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

    def test_inspection_lists_events_responses_style_and_framework(self) -> None:
        app = self._make_app()
        created = self._start(app)
        app.update_learning_response_style_payload({"care_style": "soft"}, session_id=created["id"])
        app.update_learning_session_runtime_payload(created["id"], {"action": "focus_completed", "elapsed_minutes": 15, "remaining_minutes": 0})
        events = app.list_learning_session_events_payload(created["id"])["items"]
        responses = app.list_learning_session_responses_payload(created["id"])["items"]
        style = app.get_learning_response_style_payload(created["id"])["style"]
        framework = app.get_learning_response_framework_payload(created["id"])["framework"]
        self.assertGreaterEqual(len(events), 2)
        self.assertGreaterEqual(len(responses), 1)
        self.assertEqual(style["care_style"], "soft")
        self.assertIn("layered_persona", framework)
        self.assertEqual(responses[0]["response_context"]["safety"]["explicit_language_allowed"], False)
        self.assertIn("inspection", framework)
        self.assertEqual(framework["inspection"]["effective_style"]["care_style"], "soft")
        self.assertGreaterEqual(len(framework["inspection"]["recent_events"]), 1)
        self.assertGreaterEqual(len(framework["inspection"]["recent_responses"]), 1)

    def test_framework_is_persona_ready_without_custom_persona_content(self) -> None:
        app = self._make_app()
        created = self._start(app, mode="review")
        framework = app.get_learning_response_framework_payload(created["id"])["framework"]
        self.assertEqual(framework["layered_persona"]["base_persona_slot"], "neutral_companion")
        self.assertEqual(framework["mode_overlay"], "study_review")
        self.assertIn("flattening stored config", framework["todo"])

    def test_persona_layers_are_visible_in_framework_and_inspection(self) -> None:
        app = self._make_app()
        created = self._start(app)
        framework = app.get_learning_response_framework_payload(created["id"])["framework"]
        self.assertIn("persona_composition", framework)
        self.assertIn("base_persona", framework["layered_persona"]["active_layers"])
        self.assertEqual(framework["inspection"]["persona_layers"]["partner_name"], "Aelios")
        self.assertFalse(framework["inspection"]["recovery_overlay_applied"])

    def test_recovery_overlay_only_applies_when_recovery_state_requires_it(self) -> None:
        responder = StudyCompanionResponder()
        style = responder.normalize_style(None)
        layers = StudyPersonaLayers(
            base_persona="冷静稳住",
            study_overlay="学习时压缩目标",
            recovery_overlay="恢复时先缓下来",
            safety_notes="禁止羞辱",
            style_config=style.__dict__,
        )
        stable = responder.compose_persona_layers(
            mode="focus", recovery_state="stable", style=style, persona_layers=layers
        )
        fragile = responder.compose_persona_layers(
            mode="focus", recovery_state="low_energy", style=style, persona_layers=layers
        )
        self.assertNotIn("recovery_overlay", stable["active_layers"])
        self.assertIn("recovery_overlay", fragile["active_layers"])

    def test_persona_content_affects_generated_responses_without_replacing_templates(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="session_started",
            session={"mode": "focus", "title": "线代复习", "goal": "先做两道题"},
            style=responder.normalize_style({"care_style": "steady"}),
            persona_layers=StudyPersonaLayers(
                base_persona="像可靠队友一样稳稳陪着你",
                study_overlay="学习时短句提醒",
                recovery_overlay="",
                safety_notes="禁止羞辱",
                style_config={},
            ),
        )
        self.assertIn("像可靠队友一样稳稳陪着你", plan.message)
        self.assertIn("先做两道题", plan.message)

    def test_unsafe_persona_wording_does_not_bypass_study_safety(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="session_started",
            session={"mode": "focus", "title": "英语", "goal": "背 5 个单词"},
            style=responder.normalize_style({"dominance_style": "high", "correction_style": "firm"}),
            wellbeing={"stress_level": 5, "energy_level": 1},
            persona_layers=StudyPersonaLayers(
                base_persona="punish and shame",
                study_overlay="学习时别停",
                recovery_overlay="恢复时也别羞辱",
                safety_notes="禁止惩罚",
                style_config={},
            ),
        )
        self.assertNotIn("punish", plan.message.lower())
        self.assertEqual(plan.debug["style_effects"]["pressure_override"], "softened_for_recovery")
        self.assertTrue(plan.debug["persona_composition"]["recovery_overlay_applied"])

    def test_missing_optional_persona_layers_are_handled_cleanly(self) -> None:
        responder = StudyCompanionResponder()
        plan = responder.build_response_plan(
            event_type="focus_completed",
            session={"mode": "focus", "title": "复盘", "goal": "看错题"},
            style=responder.normalize_style(None),
            persona_layers=StudyPersonaLayers(style_config={}),
        )
        self.assertTrue(plan.message)
        self.assertEqual(plan.debug["persona_composition"]["active_layers"], ["style_config"])

    def test_persona_config_syncs_legacy_fields_for_backward_compatibility(self) -> None:
        persona = PersonaConfig(core_identity="旧核心气质", boundaries="旧边界")
        self.assertEqual(persona.base_persona, "旧核心气质")
        self.assertEqual(persona.safety_notes, "旧边界")
        persona.apply_update({"base_persona": "新基础人设", "safety_notes": "新安全备注"})
        self.assertEqual(persona.core_identity, "新基础人设")
        self.assertEqual(persona.boundaries, "新安全备注")




class LearningProgressSummaryTests(unittest.TestCase):
    def _make_runtime_store(self) -> RuntimeStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        return RuntimeStore(base / "gateway.db", base / "events.jsonl")

    def _make_app(self) -> GatewayApp:
        app = GatewayApp.__new__(GatewayApp)
        app.runtime_store = self._make_runtime_store()
        app.config_store = SimpleNamespace(config=AppConfig())
        app.memory_store = SimpleNamespace(upsert_memory=lambda **kwargs: None)
        app._refresh_active_memory = lambda: None
        app._events = []
        app._record_event = lambda event_type, payload, **kwargs: app._events.append((event_type, payload))
        app.study_responder = StudyCompanionResponder()
        app.study_progress = StudyProgressSummarizer()
        return app

    def _create_sample_history(self, app: GatewayApp) -> None:
        first = app.create_learning_session_payload(
            {
                "title": "数学冲刺",
                "goal": "做题",
                "planned_minutes": 25,
                "started_at": "2026-03-18T09:00:00",
                "start_checkin": {"stage": "start", "energy_level": 2, "stress_level": 4, "note": "有点累"},
            }
        )["item"]
        app.update_learning_session_runtime_payload(first["id"], {"action": "pause", "elapsed_minutes": 8, "remaining_minutes": 17})
        app.update_learning_session_runtime_payload(first["id"], {"action": "paused_too_long"})
        app.abandon_learning_session_payload(
            first["id"],
            {"ended_at": "2026-03-18T09:08:00", "actual_minutes": 8, "summary": "状态差", "blockers": "太累, 分心", "next_step": "午后再试"},
        )

        second = app.create_learning_session_payload(
            {
                "title": "英语复盘",
                "goal": "看错题",
                "mode": "review",
                "planned_minutes": 20,
                "started_at": "2026-03-19T09:00:00",
            }
        )["item"]
        app.complete_learning_session_payload(
            second["id"],
            {"ended_at": "2026-03-19T09:20:00", "actual_minutes": 20, "summary": "完成复盘", "blockers": "速度慢"},
        )

        third = app.create_learning_session_payload(
            {
                "title": "恢复段",
                "goal": "缓一缓",
                "mode": "recovery",
                "planned_minutes": 15,
                "started_at": "2026-03-20T09:00:00",
                "start_checkin": {"stage": "start", "energy_level": 1, "body_state_level": 2, "note": "头痛，先缓缓"},
            }
        )["item"]
        app.complete_learning_session_payload(
            third["id"],
            {
                "ended_at": "2026-03-20T09:15:00",
                "actual_minutes": 15,
                "summary": "恢复完成",
                "end_checkin": {"stage": "end", "energy_level": 4, "stress_level": 2, "note": "好一点"},
            },
        )

        fourth = app.create_learning_session_payload(
            {
                "title": "短冲刺",
                "goal": "再试10分钟",
                "planned_minutes": 10,
                "pomodoro_count": 3,
                "started_at": "2026-03-21T08:00:00",
                "start_checkin": {"stage": "start", "energy_level": 2, "stress_level": 5, "note": "还是累"},
            }
        )["item"]
        app.update_learning_session_runtime_payload(fourth["id"], {"action": "pause", "elapsed_minutes": 6, "remaining_minutes": 4})
        app.update_learning_session_runtime_payload(fourth["id"], {"action": "paused_too_long"})
        app.abandon_learning_session_payload(
            fourth["id"],
            {"ended_at": "2026-03-21T08:06:00", "actual_minutes": 6, "summary": "没顶住", "blockers": "太累, 分心"},
        )

    def test_progress_summary_metrics_and_completion_rate(self) -> None:
        app = self._make_app()
        self._create_sample_history(app)
        payload = app.get_learning_progress_payload(window_days=7, session_limit=20)
        self.assertEqual(payload["metrics"]["sessions_started"], 4)
        self.assertEqual(payload["metrics"]["sessions_completed"], 2)
        self.assertEqual(payload["metrics"]["sessions_abandoned"], 2)
        self.assertEqual(payload["metrics"]["completion_rate"], 0.5)
        self.assertEqual(payload["metrics"]["total_focus_minutes"], 34)
        self.assertEqual(payload["metrics"]["average_completed_session_length_minutes"], 17.5)

    def test_focus_vs_recovery_ratio_is_inspectable(self) -> None:
        app = self._make_app()
        self._create_sample_history(app)
        payload = app.get_learning_progress_payload(window_days=7, session_limit=20)
        totals = payload["focus_balance"]["totals"]
        ratios = payload["focus_balance"]["ratios"]
        self.assertEqual(totals["focus_minutes"], 14)
        self.assertEqual(totals["review_minutes"], 20)
        self.assertEqual(totals["recovery_minutes"], 15)
        self.assertAlmostEqual(ratios["focus_ratio"], round(14 / 49, 3))
        self.assertIn("actual_minutes", payload["focus_balance"]["approximation"])

    def test_friction_pattern_detection_and_rule_traces(self) -> None:
        app = self._make_app()
        self._create_sample_history(app)
        payload = app.get_learning_progress_payload(window_days=7, session_limit=20)
        patterns = {item["pattern"]: item for item in payload["friction_patterns"]["patterns"]}
        self.assertIn("frequent_long_pauses", patterns)
        self.assertIn("repeated_abandoned_sessions", patterns)
        self.assertIn("repeated_low_energy_starts", patterns)
        self.assertIn("many_short_incomplete_attempts", patterns)
        self.assertIn("rule", patterns["frequent_long_pauses"]["rule_trace"])

    def test_low_energy_and_recovery_needed_counts_aggregate(self) -> None:
        app = self._make_app()
        self._create_sample_history(app)
        payload = app.get_learning_progress_payload(window_days=7, session_limit=20)
        self.assertGreaterEqual(payload["metrics"]["low_energy_start_count"], 3)
        self.assertGreaterEqual(payload["metrics"]["recovery_needed_signal_count"], 2)

    def test_summary_text_generation_reflects_metrics(self) -> None:
        app = self._make_app()
        self._create_sample_history(app)
        payload = app.get_learning_progress_payload(window_days=7, session_limit=20)
        self.assertIn("4 study sessions", payload["summary_text"]["weekly_summary"])
        self.assertTrue(payload["summary_text"]["recent_pattern_summary"])
        self.assertIn("Momentum", payload["summary_text"]["momentum_check"])
        self.assertIn("focus / 20 review / 15 recovery", payload["summary_text"]["blocker_focus_balance_note"])

    def test_progress_listing_returns_multiple_windows_and_inspection_metadata(self) -> None:
        app = self._make_app()
        self._create_sample_history(app)
        payload = app.list_learning_progress_payload(windows=[7, 14], session_limit=20)
        self.assertEqual(payload["available_windows"], [7, 14])
        self.assertEqual(len(payload["items"]), 2)
        self.assertIn("inspection", payload["items"][0])
        self.assertGreaterEqual(len(payload["recent_sessions"]), 4)

    def test_progress_payload_handles_no_data(self) -> None:
        app = self._make_app()
        payload = app.get_learning_progress_payload(window_days=7, session_limit=20)
        self.assertEqual(payload["metrics"]["sessions_started"], 0)
        self.assertEqual(payload["friction_patterns"]["pattern_count"], 0)
        self.assertIn("No study sessions", payload["summary_text"]["weekly_summary"])
        self.assertFalse(payload["memory_digest_hook"]["available"])


if __name__ == "__main__":
    unittest.main()

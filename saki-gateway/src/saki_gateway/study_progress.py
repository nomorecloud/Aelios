from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence


DEFAULT_PROGRESS_WINDOWS = (7, 14, 30)


@dataclass(frozen=True)
class StudyProgressWindow:
    label: str
    start_at: str
    end_at: str
    session_limit: Optional[int] = None


class StudyProgressSummarizer:
    def build_window_payload(
        self,
        *,
        sessions: Sequence[Dict[str, Any]],
        events_by_session: Dict[str, List[Dict[str, Any]]],
        checkins_by_session: Dict[str, List[Dict[str, Any]]],
        window: StudyProgressWindow,
    ) -> Dict[str, Any]:
        normalized_sessions = [dict(item) for item in sessions]
        focus_breakdown = self._build_focus_breakdown(normalized_sessions)
        friction = self._build_friction_patterns(normalized_sessions, events_by_session, checkins_by_session)
        metrics = self._build_metrics(normalized_sessions, events_by_session, checkins_by_session, focus_breakdown)
        texts = self._build_summary_texts(metrics=metrics, focus_breakdown=focus_breakdown, friction=friction, window=window)
        digest_hook = {
            "available": metrics["sessions_started"] > 0,
            "kind": "study_progress_summary",
            "summary_text": texts["weekly_summary"],
            "window_label": window.label,
            "todo": "Future digest/memory integration can read this payload, but B4 does not auto-write long-term memory.",
        }
        return {
            "window": {
                "label": window.label,
                "start_at": window.start_at,
                "end_at": window.end_at,
                "session_limit": window.session_limit,
                "effective_session_count": len(normalized_sessions),
            },
            "metrics": metrics,
            "focus_balance": focus_breakdown,
            "friction_patterns": friction,
            "summary_text": texts,
            "sessions": normalized_sessions,
            "memory_digest_hook": digest_hook,
        }

    def build_empty_payload(self, *, window: StudyProgressWindow) -> Dict[str, Any]:
        return self.build_window_payload(
            sessions=[],
            events_by_session={},
            checkins_by_session={},
            window=window,
        )

    def _build_metrics(
        self,
        sessions: Sequence[Dict[str, Any]],
        events_by_session: Dict[str, List[Dict[str, Any]]],
        checkins_by_session: Dict[str, List[Dict[str, Any]]],
        focus_breakdown: Dict[str, Any],
    ) -> Dict[str, Any]:
        started = len(sessions)
        completed = sum(1 for item in sessions if item.get("status") == "completed")
        abandoned = sum(1 for item in sessions if item.get("status") == "abandoned")
        total_focus_minutes = 0
        completed_lengths: List[int] = []
        total_pause_count = 0
        long_pause_count = 0
        total_resume_count = 0
        low_energy_count = 0
        recovery_needed_count = 0
        short_incomplete_focus_attempts = 0
        blocker_labels: Dict[str, int] = {}

        for session in sessions:
            status = str(session.get("status", "") or "")
            mode = str(session.get("mode", "focus") or "focus")
            actual_minutes = max(0, int(session.get("actual_minutes", 0) or 0))
            planned_minutes = max(0, int(session.get("planned_minutes", 0) or 0))
            if mode != "recovery":
                total_focus_minutes += actual_minutes or max(0, int(session.get("elapsed_minutes", 0) or 0))
            if status == "completed":
                completed_lengths.append(actual_minutes or planned_minutes)
            if status != "completed" and 0 < actual_minutes <= 10:
                short_incomplete_focus_attempts += 1
            blockers = self._split_blockers(str(session.get("blockers", "") or ""))
            for blocker in blockers:
                blocker_labels[blocker] = blocker_labels.get(blocker, 0) + 1

            events = events_by_session.get(str(session.get("id", "") or ""), [])
            total_pause_count += sum(1 for event in events if event.get("event_type") == "session_paused")
            long_pause_count += sum(1 for event in events if event.get("event_type") == "session_paused_too_long")
            total_resume_count += sum(1 for event in events if event.get("event_type") == "session_resumed")
            low_energy_count += sum(1 for event in events if event.get("event_type") == "low_energy_start")
            recovery_needed_count += sum(1 for event in events if event.get("event_type") == "recovery_completion")
            if self._session_suggests_recovery(checkins_by_session.get(str(session.get("id", "") or ""), []), session):
                recovery_needed_count += 1

        completion_rate = round((completed / started), 3) if started else 0.0
        average_completed_length = round(sum(completed_lengths) / len(completed_lengths), 1) if completed_lengths else 0.0
        pause_resume_ratio = round((total_pause_count / total_resume_count), 3) if total_resume_count else float(total_pause_count)
        pause_resume_friction_score = round(((long_pause_count * 2) + max(total_pause_count - total_resume_count, 0)) / max(started, 1), 3) if started else 0.0
        top_blockers = [
            {"label": label, "count": count}
            for label, count in sorted(blocker_labels.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        return {
            "sessions_started": started,
            "sessions_completed": completed,
            "sessions_abandoned": abandoned,
            "total_focus_minutes": total_focus_minutes,
            "total_recovery_minutes": focus_breakdown["totals"]["recovery_minutes"],
            "total_review_minutes": focus_breakdown["totals"]["review_minutes"],
            "completion_rate": completion_rate,
            "average_completed_session_length_minutes": average_completed_length,
            "pause_resume": {
                "pause_count": total_pause_count,
                "resume_count": total_resume_count,
                "long_pause_count": long_pause_count,
                "pause_to_resume_ratio": pause_resume_ratio,
                "friction_score": pause_resume_friction_score,
                "approximation": "Pause/resume friction uses explicit pause-related events; it does not infer silent app-idle time.",
            },
            "low_energy_start_count": low_energy_count,
            "recovery_needed_signal_count": recovery_needed_count,
            "short_incomplete_focus_attempts": short_incomplete_focus_attempts,
            "top_blockers": top_blockers,
        }

    def _build_focus_breakdown(self, sessions: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        totals = {"focus_minutes": 0, "review_minutes": 0, "recovery_minutes": 0}
        approximations: List[str] = []
        for session in sessions:
            mode = str(session.get("mode", "focus") or "focus")
            actual_minutes = max(0, int(session.get("actual_minutes", 0) or 0))
            elapsed_minutes = max(0, int(session.get("elapsed_minutes", 0) or 0))
            minutes = actual_minutes or elapsed_minutes or max(0, int(session.get("planned_minutes", 0) or 0))
            if actual_minutes <= 0:
                approximations.append(f"{session.get('id', '')}: used elapsed/planned minutes because actual_minutes was empty.")
            if mode == "review":
                totals["review_minutes"] += minutes
            elif mode == "recovery":
                totals["recovery_minutes"] += minutes
            else:
                totals["focus_minutes"] += minutes
        grand_total = sum(totals.values())
        ratios = {
            key.replace("_minutes", "_ratio"): round((value / grand_total), 3) if grand_total else 0.0
            for key, value in totals.items()
        }
        return {
            "totals": totals,
            "ratios": ratios,
            "approximation": "Time split is session-level and based on actual_minutes when present, otherwise elapsed_minutes or planned_minutes.",
            "approximation_notes": approximations[:10],
        }

    def _build_friction_patterns(
        self,
        sessions: Sequence[Dict[str, Any]],
        events_by_session: Dict[str, List[Dict[str, Any]]],
        checkins_by_session: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        rules: List[Dict[str, Any]] = []
        started = len(sessions)
        abandoned = [item for item in sessions if item.get("status") == "abandoned"]
        long_pause_sessions = []
        low_energy_sessions = []
        recovery_spike_sessions = []
        short_incomplete = []
        strain_after_pomodoros = []

        for session in sessions:
            session_id = str(session.get("id", "") or "")
            events = events_by_session.get(session_id, [])
            checkins = checkins_by_session.get(session_id, [])
            long_pause_count = sum(1 for event in events if event.get("event_type") == "session_paused_too_long")
            if long_pause_count >= 1:
                long_pause_sessions.append({"session_id": session_id, "count": long_pause_count})
            if sum(1 for event in events if event.get("event_type") == "low_energy_start") >= 1:
                low_energy_sessions.append(session_id)
            if self._session_suggests_recovery(checkins, session):
                recovery_spike_sessions.append(session_id)
            if session.get("status") != "completed" and 0 < int(session.get("actual_minutes", 0) or 0) <= 10:
                short_incomplete.append(session_id)
            if int(session.get("pomodoro_count", 0) or 0) >= 3 and (long_pause_count >= 1 or session.get("status") == "abandoned"):
                strain_after_pomodoros.append(session_id)

        if started and len(long_pause_sessions) >= 2:
            rules.append({
                "pattern": "frequent_long_pauses",
                "label": "Frequent long pauses",
                "severity": "moderate",
                "reason": f"{len(long_pause_sessions)} sessions had at least one session_paused_too_long event.",
                "rule_trace": {
                    "rule": "trigger when >=2 sessions in window contain session_paused_too_long",
                    "matched_sessions": long_pause_sessions,
                },
            })
        if started and len(abandoned) >= 2:
            rules.append({
                "pattern": "repeated_abandoned_sessions",
                "label": "Repeated abandoned sessions",
                "severity": "moderate",
                "reason": f"{len(abandoned)} sessions ended as abandoned in this window.",
                "rule_trace": {
                    "rule": "trigger when >=2 sessions are abandoned",
                    "matched_sessions": [item.get("id") for item in abandoned],
                },
            })
        if len(low_energy_sessions) >= 2:
            rules.append({
                "pattern": "repeated_low_energy_starts",
                "label": "Repeated low-energy starts",
                "severity": "gentle_watch",
                "reason": f"{len(low_energy_sessions)} sessions began with low_energy_start signals.",
                "rule_trace": {
                    "rule": "trigger when >=2 sessions include low_energy_start",
                    "matched_sessions": low_energy_sessions,
                },
            })
        if len(recovery_spike_sessions) >= 2:
            rules.append({
                "pattern": "recovery_needed_spike",
                "label": "Recovery-needed signals spiked",
                "severity": "gentle_watch",
                "reason": f"{len(recovery_spike_sessions)} sessions showed explicit low-energy/high-stress or recovery-first signals.",
                "rule_trace": {
                    "rule": "trigger when >=2 sessions meet recovery-needed heuristic",
                    "matched_sessions": recovery_spike_sessions,
                },
            })
        if len(short_incomplete) >= 2:
            rules.append({
                "pattern": "many_short_incomplete_attempts",
                "label": "Many short incomplete focus attempts",
                "severity": "gentle_watch",
                "reason": f"{len(short_incomplete)} sessions ended incomplete within 10 minutes.",
                "rule_trace": {
                    "rule": "trigger when >=2 incomplete sessions have actual_minutes <= 10",
                    "matched_sessions": short_incomplete,
                },
            })
        if len(strain_after_pomodoros) >= 1:
            rules.append({
                "pattern": "strain_after_multiple_pomodoros",
                "label": "Strain after multiple pomodoros",
                "severity": "watch",
                "reason": f"{len(strain_after_pomodoros)} session(s) with pomodoro_count >= 3 later hit a long pause or abandonment.",
                "rule_trace": {
                    "rule": "trigger when pomodoro_count >=3 and session has long pause or is abandoned",
                    "matched_sessions": strain_after_pomodoros,
                },
            })
        return {
            "patterns": rules,
            "pattern_count": len(rules),
            "note": "Rules are explicit heuristics over recent session/check-in/event data and are not diagnostic claims.",
        }

    def _build_summary_texts(
        self,
        *,
        metrics: Dict[str, Any],
        focus_breakdown: Dict[str, Any],
        friction: Dict[str, Any],
        window: StudyProgressWindow,
    ) -> Dict[str, str]:
        started = metrics["sessions_started"]
        completed = metrics["sessions_completed"]
        if started == 0:
            empty = f"No study sessions were recorded in the {window.label} window yet."
            return {
                "weekly_summary": empty,
                "recent_pattern_summary": empty,
                "momentum_check": "Momentum is still unknown because there is not enough recent study data yet.",
                "blocker_focus_balance_note": "No balance or blocker trend can be summarized until at least one session is recorded.",
            }
        completion_pct = int(round(metrics["completion_rate"] * 100))
        balance = focus_breakdown["totals"]
        top_patterns = [item["label"].lower() for item in friction["patterns"][:2]]
        blocker_text = ", ".join(item["label"] for item in metrics["top_blockers"][:2]) or "no repeated blocker text yet"
        weekly_summary = (
            f"In the {window.label} window there were {started} study sessions, with {completed} completed "
            f"({completion_pct}% completion) and {metrics['total_focus_minutes']} focus minutes logged."
        )
        if metrics["low_energy_start_count"]:
            weekly_summary += f" Low-energy starts showed up {metrics['low_energy_start_count']} time(s)."
        pattern_summary = (
            f"Recent patterns suggest {', '.join(top_patterns)}."
            if top_patterns
            else "Recent patterns are fairly steady, without a strong repeated friction signal yet."
        )
        if metrics["sessions_abandoned"] and not top_patterns:
            pattern_summary = f"Recent patterns show {metrics['sessions_abandoned']} abandoned session(s), but no broader repeated rule has fired yet."
        if completion_pct >= 70 and metrics["sessions_abandoned"] <= 1:
            momentum = "Momentum looks reasonably steady right now."
        elif completion_pct >= 40:
            momentum = "Momentum is mixed: starts are happening, but follow-through is uneven."
        else:
            momentum = "Momentum looks fragile right now, so smaller repeatable sessions may fit better than pushing longer blocks."
        balance_note = (
            f"Recent time split was {balance['focus_minutes']} focus / {balance['review_minutes']} review / "
            f"{balance['recovery_minutes']} recovery minutes; recurring blocker notes mention {blocker_text}."
        )
        return {
            "weekly_summary": weekly_summary,
            "recent_pattern_summary": pattern_summary,
            "momentum_check": momentum,
            "blocker_focus_balance_note": balance_note,
        }

    def _session_suggests_recovery(self, checkins: Iterable[Dict[str, Any]], session: Dict[str, Any]) -> bool:
        notes = " ".join(str(item.get("note", "") or "") for item in checkins).lower()
        recovery_words = ("recover", "rest", "累", "焦虑", "头痛", "不舒服", "缓")
        if any(word in notes for word in recovery_words):
            return True
        for item in checkins:
            energy = item.get("energy_level")
            stress = item.get("stress_level")
            body_state = item.get("body_state_level")
            if energy is not None and int(energy) <= 2:
                return True
            if stress is not None and int(stress) >= 4:
                return True
            if body_state is not None and int(body_state) <= 2:
                return True
        return str(session.get("mode", "focus") or "focus") == "recovery"

    def _split_blockers(self, value: str) -> List[str]:
        normalized = value.replace("；", ",").replace(";", ",").replace("、", ",")
        items = [part.strip() for part in normalized.split(",")]
        return [item for item in items if item][:5]


def iso_utc_now() -> datetime:
    return datetime.utcnow()


def make_window(*, days: int, now: Optional[datetime] = None, session_limit: Optional[int] = None) -> StudyProgressWindow:
    current = now or iso_utc_now()
    start = current - timedelta(days=max(days, 1))
    return StudyProgressWindow(
        label=f"last {max(days, 1)} days",
        start_at=start.isoformat(),
        end_at=current.isoformat(),
        session_limit=session_limit,
    )

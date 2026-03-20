from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional


SAFE_BANNED_TERMS = {
    "pathetic",
    "lazy pig",
    "useless",
    "disgusting",
    "worthless",
    "punish",
    "punishment",
    "humiliate",
    "humiliating",
    "slut",
    "idiot",
    "stupid",
}


@dataclass(frozen=True)
class StudyResponseStyle:
    dominance_style: str = "medium"
    care_style: str = "steady"
    praise_style: str = "warm"
    correction_style: str = "gentle"


DEFAULT_STUDY_RESPONSE_STYLE = StudyResponseStyle()


ALLOWED_STYLE_VALUES = {
    "dominance_style": {"low", "medium", "high"},
    "care_style": {"soft", "steady", "strict_care"},
    "praise_style": {"restrained", "warm", "possessive_lite"},
    "correction_style": {"gentle", "firm"},
}


class StudyCompanionResponder:
    def normalize_style(self, payload: Optional[Dict[str, Any]]) -> StudyResponseStyle:
        base = asdict(DEFAULT_STUDY_RESPONSE_STYLE)
        if isinstance(payload, dict):
            for key, allowed in ALLOWED_STYLE_VALUES.items():
                value = str(payload.get(key, "") or "").strip().lower()
                if value in allowed:
                    base[key] = value
        return StudyResponseStyle(**base)

    def build_message(
        self,
        *,
        event_type: str,
        session: Dict[str, Any],
        style: StudyResponseStyle,
        wellbeing: Optional[Dict[str, Any]] = None,
        recent_events: Optional[Iterable[Dict[str, Any]]] = None,
        persona_context: str = "",
    ) -> str:
        wellbeing = wellbeing or {}
        mode = str(session.get("mode", "focus") or "focus")
        title = str(session.get("title", "") or "").strip()
        goal = str(session.get("goal", "") or "").strip()
        energy = self._level(wellbeing.get("energy_level"))
        stress = self._level(wellbeing.get("stress_level"))
        body = self._level(wellbeing.get("body_state_level"))
        overwhelmed = self._is_overwhelmed(energy, stress, body, wellbeing)
        firm = self._should_be_firm(style, event_type, overwhelmed)
        subject = title or session.get("subject") or "这轮学习"
        anchor = goal or subject

        if event_type == "session_started":
            if overwhelmed:
                return self._safe(f"先别急，我们把目标缩成 {anchor} 的最小一步，稳稳开始就够了。")
            opening = "开始吧，我陪你把这段专注守住。" if not firm else "开始了，先把注意力收回来，我们只做眼前这一段。"
            return self._safe(f"{opening} 先盯住 {anchor}。")
        if event_type == "low_energy_start":
            return self._safe("我知道你现在状态不满格。先做最小的一步，撑不住就告诉我，我们立刻降强度。")
        if event_type == "focus_completed":
            praise = "做得好，我看到了。" if style.praise_style != "restrained" else "这段完成了。"
            addon = " 先呼吸一下，再决定要不要继续。" if overwhelmed else " 这一段你是稳住了的。"
            return self._safe(f"{praise}{addon}")
        if event_type == "break_started":
            return self._safe("现在进休息段。离开题目一会儿，喝水、活动肩颈，等下我们再接上。")
        if event_type == "break_completed":
            return self._safe("休息够了，回来就只抓下一小段，不需要一下子把全部状态找齐。")
        if event_type == "session_paused":
            return self._safe("先暂停也可以。把这次停下的原因记住，等你回来我帮你重新接住节奏。")
        if event_type == "session_paused_too_long":
            if overwhelmed:
                return self._safe("你已经停了有一会儿。如果还是很累，我们就把目标再缩小，或者今天先体面收尾。")
            return self._safe("你停得有点久了。现在回来做五分钟也算重启，不要继续往后拖。")
        if event_type == "session_resumed":
            return self._safe("欢迎回来。别补偿式猛冲，先把手上的下一步做完。")
        if event_type == "session_completed":
            praise = "很好，我为你高兴。" if style.praise_style == "warm" else "完成了。"
            if style.praise_style == "possessive_lite":
                praise = "很好，这段你乖乖做完了。"
            return self._safe(f"{praise} 这一轮可以收下了，记得按 {anchor} 的方向接上下一步。")
        if event_type == "session_abandoned":
            if overwhelmed:
                return self._safe("今天先停在这里也没关系。先照顾状态，我们之后只接一个更小的下一步。")
            return self._safe("这轮先收住，不算失败。把卡点留给我，我们下一次直接从最小可做步骤重新开始。")
        if event_type == "recovery_completion":
            return self._safe("恢复段完成了，这就很重要。先确认你稳一点了，再决定要不要继续推进。")
        return self._safe("我在。我们按下一步继续，不急着一下子做很多。")

    def _level(self, value: Any) -> Optional[int]:
        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _is_overwhelmed(
        self,
        energy: Optional[int],
        stress: Optional[int],
        body: Optional[int],
        wellbeing: Dict[str, Any],
    ) -> bool:
        note = str(wellbeing.get("note", "") or "").lower()
        flagged_words = ("overwhelmed", "panic", "anxious", "sick", "ill", "痛", "累", "难受", "焦虑", "撑不住")
        if any(word in note for word in flagged_words):
            return True
        return (energy is not None and energy <= 2) or (stress is not None and stress >= 4) or (body is not None and body <= 2)

    def _should_be_firm(self, style: StudyResponseStyle, event_type: str, overwhelmed: bool) -> bool:
        if overwhelmed:
            return False
        if style.dominance_style == "high" or style.correction_style == "firm":
            return event_type in {"session_started", "session_paused_too_long", "session_resumed"}
        return False

    def _safe(self, text: str) -> str:
        sanitized = " ".join(str(text or "").split())
        lowered = sanitized.lower()
        for term in SAFE_BANNED_TERMS:
            if term in lowered:
                raise ValueError(f"unsafe_study_response:{term}")
        return sanitized[:220]

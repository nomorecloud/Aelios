from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional


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

SAFE_EXPLICIT_TERMS = {
    "fuck",
    "性爱",
    "sexual",
    "erotic",
    "色情",
    "调教",
}


@dataclass(frozen=True)
class StudyResponseStyle:
    dominance_style: str = "medium"
    care_style: str = "steady"
    praise_style: str = "warm"
    correction_style: str = "gentle"


@dataclass(frozen=True)
class LayeredPersonaSlots:
    base_persona_slot: str = "neutral_companion"
    context_overlay_slot: str = "study_focus"
    event_response_style_slot: str = "brief_supportive"
    safety_boundary_slot: str = "study_safe_boundaries"


@dataclass(frozen=True)
class ResponseGenerationPlan:
    message: str
    debug: Dict[str, Any]


DEFAULT_STUDY_RESPONSE_STYLE = StudyResponseStyle()
DEFAULT_LAYERED_PERSONA_SLOTS = LayeredPersonaSlots()


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

    def describe_framework(
        self,
        *,
        session: Optional[Dict[str, Any]] = None,
        style: Optional[StudyResponseStyle] = None,
        wellbeing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = session or {}
        wellbeing = wellbeing or {}
        normalized_style = style or DEFAULT_STUDY_RESPONSE_STYLE
        mode = str(session.get("mode", "focus") or "focus")
        energy = self._level(wellbeing.get("energy_level"))
        stress = self._level(wellbeing.get("stress_level"))
        body = self._level(wellbeing.get("body_state_level"))
        overwhelmed = self._is_overwhelmed(energy, stress, body, wellbeing)
        layer_slots = DEFAULT_LAYERED_PERSONA_SLOTS
        context_overlay = {
            "focus": "study_focus",
            "recovery": "study_recovery",
            "review": "study_review",
        }.get(mode, "study_focus")
        return {
            "layered_persona": {
                **asdict(layer_slots),
                "context_overlay_slot": context_overlay,
            },
            "mode_overlay": context_overlay,
            "style": asdict(normalized_style),
            "wellbeing_signal": {
                "energy_level": energy,
                "stress_level": stress,
                "body_state_level": body,
                "overwhelmed": overwhelmed,
            },
            "style_effects": self._style_effects(normalized_style, overwhelmed=overwhelmed),
            "safety": {
                "explicit_language_allowed": False,
                "degrading_language_allowed": False,
                "intimate_or_rp_allowed": False,
                "prefer_smaller_steps_when_overwhelmed": True,
                "future_rule_extension": "Add mode-specific safety rules alongside this layer instead of mixing them into persona text.",
            },
            "todo": "Future persona injection should fill the layer slots without replacing the event framework.",
        }

    def build_response_plan(
        self,
        *,
        event_type: str,
        session: Dict[str, Any],
        style: StudyResponseStyle,
        wellbeing: Optional[Dict[str, Any]] = None,
        recent_events: Optional[Iterable[Dict[str, Any]]] = None,
        persona_context: str = "",
    ) -> ResponseGenerationPlan:
        wellbeing = wellbeing or {}
        recent_events = list(recent_events or [])
        title = str(session.get("title", "") or "").strip()
        goal = str(session.get("goal", "") or "").strip()
        subject = title or session.get("subject") or "这轮学习"
        anchor = goal or subject
        mode = str(session.get("mode", "focus") or "focus")
        energy = self._level(wellbeing.get("energy_level"))
        stress = self._level(wellbeing.get("stress_level"))
        body = self._level(wellbeing.get("body_state_level"))
        overwhelmed = self._is_overwhelmed(energy, stress, body, wellbeing)
        recent_event_types = [str(item.get("event_type", "") or "") for item in recent_events[:5]]
        recent_repeated = self._recent_repetition_count(event_type, recent_event_types)
        firm = self._should_be_firm(style, event_type, overwhelmed)
        context = self.describe_framework(session=session, style=style, wellbeing=wellbeing)
        context["persona_context"] = str(persona_context or "").strip()
        context["recent_event_types"] = recent_event_types
        context["recent_repetition_count"] = recent_repeated
        context["event_type"] = event_type
        context["anchor"] = anchor
        context["session_mode"] = mode
        message, selection_debug = self._build_message_text(
            event_type=event_type,
            mode=mode,
            anchor=anchor,
            style=style,
            overwhelmed=overwhelmed,
            firm=firm,
            recent_repetition_count=recent_repeated,
        )
        context["response_selection"] = selection_debug
        return ResponseGenerationPlan(message=self._safe(message), debug=context)

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
        return self.build_response_plan(
            event_type=event_type,
            session=session,
            style=style,
            wellbeing=wellbeing,
            recent_events=recent_events,
            persona_context=persona_context,
        ).message

    def _build_message_text(
        self,
        *,
        event_type: str,
        mode: str,
        anchor: str,
        style: StudyResponseStyle,
        overwhelmed: bool,
        firm: bool,
        recent_repetition_count: int,
    ) -> tuple[str, Dict[str, Any]]:
        variants = self._event_variants(
            event_type=event_type,
            mode=mode,
            anchor=anchor,
            style=style,
            overwhelmed=overwhelmed,
            firm=firm,
        )
        index = min(max(recent_repetition_count, 0), len(variants) - 1)
        return variants[index], {
            "candidate_count": len(variants),
            "selected_index": index,
            "recent_repetition_count": recent_repetition_count,
        }

    def _event_variants(
        self,
        *,
        event_type: str,
        mode: str,
        anchor: str,
        style: StudyResponseStyle,
        overwhelmed: bool,
        firm: bool,
    ) -> List[str]:
        care_prefix = self._care_prefix(style, overwhelmed=overwhelmed)
        correction_hint = self._correction_hint(style, overwhelmed=overwhelmed)
        praise = self._praise_phrase(style)
        praise_completion = self._completion_praise(style)
        if event_type == "session_started":
            variants = [
                f"{care_prefix}先盯住 {anchor}，我们把开头压到最小也可以。",
                f"开始吧，先守住 {anchor} 的这一小段，别急着做很多。",
                f"{correction_hint}先把注意力收回来，只做 {anchor} 这一段。",
            ]
            if mode == "review":
                variants = [
                    f"开始吧，先把复盘范围压小，只盯住 {anchor}。",
                    f"先别铺太开，复盘时只看 {anchor} 这一处关键点。",
                    f"复盘先收窄范围，我们只处理 {anchor}，够了再扩。",
                ]
            elif mode == "recovery":
                variants = [
                    f"恢复段开始了。先做 {anchor} 的最轻一步，把状态慢慢接上。",
                    f"现在按恢复节奏来，只碰 {anchor} 这一小块就好。",
                    f"今天先求稳，{anchor} 做一点就算顺利起步。",
                ]
            if overwhelmed:
                variants = [
                    f"先别急，我们把目标缩成 {anchor} 的最小一步，稳稳开始就够了。",
                    f"现在不追求满状态，只把 {anchor} 拆成最小动作就行。",
                    f"你先把负担放低，只做 {anchor} 的第一小步，我陪你稳住。",
                ]
            return variants
        if event_type == "low_energy_start":
            return [
                "我知道你现在状态不满格。先做最小的一步，撑不住就告诉我，我们立刻降强度。",
                "先别硬顶。今天只拿下最小动作，觉得吃力就马上收缩目标。",
                "你现在更需要稳住，不需要逞强。先做一点点，难受就及时停下来。",
            ]
        if event_type == "focus_completed":
            addon = "先呼吸一下，再决定要不要继续。" if overwhelmed else "这一段你是稳住了的。"
            if mode == "review":
                addon = "先记下一个关键发现，再决定下一段看哪里。"
            return [
                f"{praise}{addon}",
                f"{praise}先停一秒，把这一段收好，我们再接下一步。",
                f"{praise}这一轮已经落地，接下来只需要续上最小下一步。",
            ]
        if event_type == "break_started":
            break_kind = "长休息" if style.care_style == "soft" or overwhelmed else "休息段"
            if mode == "recovery":
                return [
                    f"现在进恢复段。先离开题目一会儿，喝水、活动肩颈，等稳一点我们再接。",
                    f"恢复优先。先把 {break_kind} 用来缓一缓，再决定回来的力度。",
                    "先照顾身体，离开题目、喝水、活动一下，状态稳了我们再继续。",
                ]
            return [
                f"现在进{break_kind}。离开题目一会儿，喝水、活动肩颈，等下我们再接上。",
                "先休息，不要一边刷题一边硬撑。动一动、喝点水，回来只接下一小段。",
                "这会儿先把专注放下，给眼睛和肩颈一点空间，待会儿再续。",
            ]
        if event_type == "break_completed":
            if mode == "review":
                return [
                    "休息够了，回来只看下一处关键点，不需要一次复盘完全部内容。",
                    "回来后先看一处最关键的问题点，别把整轮复盘一次性摊开。",
                    "现在只续上一个复盘节点，保持清醒比一次看太多更重要。",
                ]
            if mode == "recovery":
                return [
                    "休息够了，回来先做最轻的一步，把状态慢慢接回来。",
                    "先别猛冲，回来只接一小段，确认身体和注意力都还跟得上。",
                    "现在回到题目前，先给自己一个很小的可完成目标。",
                ]
            return [
                "休息够了，回来就只抓下一小段，不需要一下子把全部状态找齐。",
                "现在回来只续上一个小目标，别要求自己立刻满速。",
                "重新接上节奏就好，先做最清楚的下一步。",
            ]
        if event_type == "session_paused":
            return [
                f"先暂停也可以。把这次停下的原因记住，等你回来我帮你重新接住节奏。",
                "先停一下没关系。回来时我们直接从最小下一步重新起。",
                "暂停不是掉线，等你回来我们就把节奏重新接起来。",
            ]
        if event_type == "session_paused_too_long":
            if overwhelmed:
                return [
                    "你已经停了有一会儿。如果还是很累，我们就把目标再缩小，或者今天先体面收尾。",
                    "停得久也没关系，先判断自己是不是还撑得住；不行就把目标降到更小。",
                    "如果现在还是低能量，我们只重启一小步，或者直接好好收尾。",
                ]
            if firm:
                return [
                    "你停得有点久了。现在回来做五分钟也算重启，不要继续往后拖。",
                    "这会儿该把节奏接回来了。先做五分钟，别再让停顿继续扩大。",
                    "先回来完成一个最小动作，别把重启这件事一直往后放。",
                ]
            return [
                "你已经停了一阵。现在回来做一小步就够，我们先把节奏接回去。",
                "停顿已经够长了，回来只做最小下一步就算赢。",
                "先别评判这次停顿，回来接上一小段，我们就继续。",
            ]
        if event_type == "session_resumed":
            if mode == "recovery":
                return [
                    "欢迎回来。别补偿式猛冲，先做最轻的一步，把状态慢慢接回来。",
                    "回来就好，先用最轻的节奏热身，不需要追赶刚才的停顿。",
                    "先接一小步，确认自己跟得上，再决定要不要继续加力。",
                ]
            return [
                f"欢迎回来。{correction_hint}先把手上的下一步做完。",
                "回来就继续，但只抓眼前这一步，不需要追求立刻满速。",
                "重新接上就很好，先完成一个清楚的小动作。",
            ]
        if event_type == "session_completed":
            return [
                f"{praise_completion}这一轮可以收下了，记得按 {anchor} 的方向接上下一步。",
                f"{praise_completion}今天这段已经落袋，之后按 {anchor} 再续就行。",
                f"{praise_completion}这轮先稳稳收住，下一次直接从 {anchor} 的下一步接。",
            ]
        if event_type == "session_abandoned":
            if overwhelmed:
                return [
                    "今天先停在这里也没关系。先照顾状态，我们之后只接一个更小的下一步。",
                    "先把自己照顾好，学习可以晚一点再接；下次只从更小的步骤开始。",
                    "这一轮先放下也可以，等状态稳一点，我们只拿回一个很小的进展。",
                ]
            return [
                "这轮先收住，不算失败。把卡点留给我，我们下一次直接从最小可做步骤重新开始。",
                "先停下也可以。记住卡住的位置，下次我们只从最容易接上的一步重启。",
                "这次先不硬撑，把阻碍留下来，之后只接一个最小可做动作。",
            ]
        if event_type == "recovery_completion":
            return [
                "恢复段完成了，这就很重要。先确认你稳一点了，再决定要不要继续推进。",
                "这次恢复本身就是进展。先看身体和心绪有没有稳住，再决定下一步。",
                "你把恢复段走完了，已经很好。接下来只在状态允许时再往前推。",
            ]
        return [
            "我在。我们按下一步继续，不急着一下子做很多。",
            "先别把目标放太大，只接眼前这一小步就好。",
            "我会陪你把节奏守住，先完成最清楚的下一步。",
        ]

    def _care_prefix(self, style: StudyResponseStyle, *, overwhelmed: bool) -> str:
        if overwhelmed or style.care_style == "soft":
            return "先缓一点，"
        if style.care_style == "strict_care":
            return "先稳住节奏，"
        return ""

    def _correction_hint(self, style: StudyResponseStyle, *, overwhelmed: bool) -> str:
        if overwhelmed:
            return "先把负担放轻，"
        if style.correction_style == "firm" or style.dominance_style == "high":
            return "先把注意力收回来，"
        if style.dominance_style == "low":
            return "慢慢来，"
        return ""

    def _praise_phrase(self, style: StudyResponseStyle) -> str:
        return {
            "restrained": "这段完成了。",
            "warm": "做得好，我看到了。",
            "possessive_lite": "很好，这一段你有稳稳跟上。",
        }.get(style.praise_style, "做得好，我看到了。")

    def _completion_praise(self, style: StudyResponseStyle) -> str:
        if style.praise_style == "warm":
            return "很好，我为你高兴。"
        if style.praise_style == "possessive_lite":
            return "很好，这段你乖乖做完了。"
        return "完成了。"

    def _recent_repetition_count(self, event_type: str, recent_event_types: List[str]) -> int:
        count = 0
        for name in recent_event_types:
            if name == event_type:
                count += 1
            else:
                break
        return count

    def _style_effects(self, style: StudyResponseStyle, *, overwhelmed: bool) -> Dict[str, Any]:
        return {
            "dominance_tone": "direct" if style.dominance_style == "high" and not overwhelmed else "measured",
            "care_tone": {
                "soft": "extra_reassurance",
                "steady": "balanced_support",
                "strict_care": "protective_structure",
            }.get(style.care_style, "balanced_support"),
            "praise_tone": {
                "restrained": "low-intensity acknowledgement",
                "warm": "encouraging acknowledgement",
                "possessive_lite": "close-but-study-safe acknowledgement",
            }.get(style.praise_style, "encouraging acknowledgement"),
            "correction_tone": "gentle_redirect" if overwhelmed or style.correction_style == "gentle" else "firm_redirect",
        }

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
        for term in SAFE_BANNED_TERMS | SAFE_EXPLICIT_TERMS:
            if term in lowered:
                raise ValueError(f"unsafe_study_response:{term}")
        return sanitized[:220]

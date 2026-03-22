from __future__ import annotations

from dataclasses import asdict, dataclass
import re
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
class StudyPersonaLayers:
    base_persona: str = ""
    study_overlay: str = ""
    recovery_overlay: str = ""
    safety_notes: str = ""
    style_config: Dict[str, Any] | None = None


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
        recent_events: Optional[Iterable[Dict[str, Any]]] = None,
        recent_responses: Optional[Iterable[Dict[str, Any]]] = None,
        persona_layers: Optional[StudyPersonaLayers] = None,
    ) -> Dict[str, Any]:
        session = session or {}
        wellbeing = wellbeing or {}
        normalized_style = style or DEFAULT_STUDY_RESPONSE_STYLE
        persona_layers = persona_layers or StudyPersonaLayers(
            style_config=asdict(normalized_style)
        )
        mode = str(session.get("mode", "focus") or "focus")
        recovery = self._interpret_recovery_state(
            session=session,
            wellbeing=wellbeing,
            recent_events=list(recent_events or []),
            recent_responses=list(recent_responses or []),
        )
        layer_slots = DEFAULT_LAYERED_PERSONA_SLOTS
        context_overlay = {
            "focus": "study_focus",
            "recovery": "study_recovery",
            "review": "study_review",
        }.get(mode, "study_focus")
        composed_persona = self.compose_persona_layers(
            mode=mode,
            recovery_state=recovery["state"],
            style=normalized_style,
            persona_layers=persona_layers,
        )
        return {
            "layered_persona": {
                **asdict(layer_slots),
                "context_overlay_slot": context_overlay,
                "configured_layers": {
                    "base_persona": bool(persona_layers.base_persona.strip()),
                    "study_overlay": bool(persona_layers.study_overlay.strip()),
                    "recovery_overlay": bool(persona_layers.recovery_overlay.strip()),
                    "safety_notes": bool(persona_layers.safety_notes.strip()),
                },
                "active_layers": composed_persona["active_layers"],
                "recovery_overlay_applied": composed_persona["recovery_overlay_applied"],
            },
            "mode_overlay": context_overlay,
            "style": asdict(normalized_style),
            "wellbeing_signal": recovery["wellbeing_signal"],
            "recovery_state": {
                "state": recovery["state"],
                "score": recovery["score"],
                "reasons": recovery["reasons"],
                "recent_friction_flags": recovery["recent_friction_flags"],
                "rule_trace": recovery["rule_trace"],
            },
            "style_effects": self._style_effects(normalized_style, recovery_state=recovery["state"]),
            "persona_composition": composed_persona,
            "safety": {
                "explicit_language_allowed": False,
                "degrading_language_allowed": False,
                "intimate_or_rp_allowed": False,
                "prefer_smaller_steps_when_overwhelmed": True,
                "prioritize_stabilization_when_fragile": True,
                "avoid_guilt_language": True,
                "future_rule_extension": "Add mode-specific safety rules alongside this layer instead of mixing them into persona text.",
            },
            "todo": "Future persona injection should add overlays/modes without replacing the event framework or flattening stored config.",
        }

    def build_response_plan(
        self,
        *,
        event_type: str,
        session: Dict[str, Any],
        style: StudyResponseStyle,
        wellbeing: Optional[Dict[str, Any]] = None,
        recent_events: Optional[Iterable[Dict[str, Any]]] = None,
        recent_responses: Optional[Iterable[Dict[str, Any]]] = None,
        persona_layers: Optional[StudyPersonaLayers] = None,
    ) -> ResponseGenerationPlan:
        wellbeing = wellbeing or {}
        recent_events = list(recent_events or [])
        recent_responses = list(recent_responses or [])
        title = str(session.get("title", "") or "").strip()
        goal = str(session.get("goal", "") or "").strip()
        subject = title or session.get("subject") or "这轮学习"
        anchor = goal or subject
        mode = str(session.get("mode", "focus") or "focus")
        recovery = self._interpret_recovery_state(
            session=session,
            wellbeing=wellbeing,
            recent_events=recent_events,
            recent_responses=recent_responses,
        )
        recovery_state = recovery["state"]
        recent_event_types = [str(item.get("event_type", "") or "") for item in recent_events[:5]]
        recent_repeated = self._recent_repetition_count(event_type, recent_event_types)
        firm = self._should_be_firm(style, event_type, recovery_state)
        next_step = self._select_next_step_category(
            recovery_state=recovery_state,
            event_type=event_type,
            session=session,
            recent_events=recent_events,
            friction_flags=recovery["recent_friction_flags"],
        )
        context = self.describe_framework(
            session=session,
            style=style,
            wellbeing=wellbeing,
            recent_events=recent_events,
            recent_responses=recent_responses,
            persona_layers=persona_layers,
        )
        context["recent_event_types"] = recent_event_types
        context["recent_repetition_count"] = recent_repeated
        context["recent_response_types"] = [str(item.get("event_type", "") or "") for item in recent_responses[:5]]
        context["event_type"] = event_type
        context["anchor"] = anchor
        context["session_mode"] = mode
        context["next_step"] = next_step
        message, selection_debug = self._build_message_text(
            event_type=event_type,
            mode=mode,
            anchor=anchor,
            style=style,
            recovery_state=recovery_state,
            firm=firm,
            recent_repetition_count=recent_repeated,
            next_step=next_step,
        )
        message = self._apply_persona_flavor(
            message,
            persona_composition=context.get("persona_composition") or {},
            recovery_state=recovery_state,
        )
        context["response_selection"] = selection_debug
        context["adaptation"] = {
            "recovery_aware": recovery_state != "stable",
            "pressure_level": self._pressure_level(recovery_state, firm),
            "response_mode": self._response_mode(recovery_state),
            "adapted_behavior": self._adapted_behavior_summary(recovery_state, next_step["category"]),
        }
        return ResponseGenerationPlan(message=self._safe(message), debug=context)

    def build_message(
        self,
        *,
        event_type: str,
        session: Dict[str, Any],
        style: StudyResponseStyle,
        wellbeing: Optional[Dict[str, Any]] = None,
        recent_events: Optional[Iterable[Dict[str, Any]]] = None,
        recent_responses: Optional[Iterable[Dict[str, Any]]] = None,
        persona_layers: Optional[StudyPersonaLayers] = None,
    ) -> str:
        return self.build_response_plan(
            event_type=event_type,
            session=session,
            style=style,
            wellbeing=wellbeing,
            recent_events=recent_events,
            recent_responses=recent_responses,
            persona_layers=persona_layers,
        ).message

    def compose_persona_layers(
        self,
        *,
        mode: str,
        recovery_state: str,
        style: StudyResponseStyle,
        persona_layers: StudyPersonaLayers,
    ) -> Dict[str, Any]:
        active_layers: List[str] = []
        resolved: List[Dict[str, str]] = []
        for name, text in (
            ("base_persona", persona_layers.base_persona),
            ("study_overlay", persona_layers.study_overlay),
        ):
            clean = str(text or "").strip()
            if clean:
                active_layers.append(name)
                resolved.append({"layer": name, "text": clean})
        recovery_applied = recovery_state != "stable" and bool(
            str(persona_layers.recovery_overlay or "").strip()
        )
        if recovery_applied:
            active_layers.append("recovery_overlay")
            resolved.append(
                {
                    "layer": "recovery_overlay",
                    "text": str(persona_layers.recovery_overlay or "").strip(),
                }
            )
        safety = str(persona_layers.safety_notes or "").strip()
        if safety:
            active_layers.append("safety_notes")
            resolved.append({"layer": "safety_notes", "text": safety})
        style_summary = (
            f"dominance={style.dominance_style}; care={style.care_style}; "
            f"praise={style.praise_style}; correction={style.correction_style}"
        )
        active_layers.append("style_config")
        resolved.append({"layer": "style_config", "text": style_summary})
        return {
            "active_layers": active_layers,
            "recovery_overlay_applied": recovery_applied,
            "resolved_layers": resolved,
            "summary": " | ".join(item["layer"] for item in resolved),
            # TODO: add future non-study overlays here instead of widening response templates.
        }

    def _apply_persona_flavor(
        self,
        message: str,
        *,
        persona_composition: Dict[str, Any],
        recovery_state: str,
    ) -> str:
        prefix = self._persona_prefix(
            persona_composition=persona_composition, recovery_state=recovery_state
        )
        if prefix:
            return f"{prefix}{message}"
        return message

    def _persona_prefix(
        self, *, persona_composition: Dict[str, Any], recovery_state: str
    ) -> str:
        text_map = {
            item.get("layer"): str(item.get("text", "") or "")
            for item in persona_composition.get("resolved_layers", [])
            if isinstance(item, dict)
        }
        source = " ".join(
            [
                text_map.get("base_persona", ""),
                text_map.get("study_overlay", ""),
                text_map.get("recovery_overlay", "") if recovery_state != "stable" else "",
            ]
        ).strip()
        if not source:
            return ""
        softened = source.lower()
        if any(term in softened for term in SAFE_BANNED_TERMS | SAFE_EXPLICIT_TERMS):
            return ""
        snippet = re.split(r"[。.!?\n；;]", source)[0].strip()
        snippet = re.sub(r"\s+", " ", snippet)
        snippet = snippet[:28].strip(" ，,;；。")
        if not snippet:
            return ""
        return f"{snippet}，"

    def _build_message_text(
        self,
        *,
        event_type: str,
        mode: str,
        anchor: str,
        style: StudyResponseStyle,
        recovery_state: str,
        firm: bool,
        recent_repetition_count: int,
        next_step: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        variants = self._event_variants(
            event_type=event_type,
            mode=mode,
            anchor=anchor,
            style=style,
            recovery_state=recovery_state,
            firm=firm,
            next_step=next_step,
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
        recovery_state: str,
        firm: bool,
        next_step: Dict[str, Any],
    ) -> List[str]:
        strained = recovery_state != "stable"
        care_prefix = self._care_prefix(style, recovery_state=recovery_state)
        correction_hint = self._correction_hint(style, recovery_state=recovery_state)
        praise = self._praise_phrase(style, recovery_state=recovery_state)
        praise_completion = self._completion_praise(style, recovery_state=recovery_state)
        next_step_text = next_step["label"]
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
            if recovery_state in {"overwhelmed", "anxious_or_stressed", "low_energy", "recovery_needed"}:
                variants = [
                    f"先别急，我们把目标缩成 {anchor} 的最小一步，先按『{next_step_text}』来。",
                    f"现在不追求满状态，只把 {anchor} 压到最小，先走『{next_step_text}』。",
                    f"你先把负担放低，只做 {anchor} 的第一小步；如果吃力，就改成『{next_step_text}』。",
                ]
            return variants
        if event_type == "low_energy_start":
            return [
                f"我先帮你降强度。现在只要『{next_step_text}』，撑不住就直接转恢复。",
                f"先别硬顶，今天先按『{next_step_text}』来，能稳住就够了。",
                f"你现在更需要回到可执行状态，不需要逞强；先做最小动作，不行就休息。",
            ]
        if event_type == "focus_completed":
            addon = "先呼吸一下，再决定要不要继续。" if strained else "这一段你是稳住了的。"
            if mode == "review":
                addon = "先记下一个关键发现，再决定下一段看哪里。"
            if recovery_state == "recovery_needed":
                addon = "这一段已经够了，优先休息恢复，不用再硬续。"
            return [
                f"{praise}{addon}",
                f"{praise}先停一秒，把这一段收好，再看要不要『{next_step_text}』。",
                f"{praise}这一轮已经落地，接下来只需要很小的下一步。",
            ]
        if event_type == "break_started":
            break_kind = "长休息" if style.care_style == "soft" or strained else "休息段"
            if mode == "recovery" or recovery_state == "recovery_needed":
                return [
                    f"现在进恢复段。先离开题目一会儿，喝水、活动肩颈，先按『{next_step_text}』。",
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
            if mode == "recovery" or strained:
                return [
                    f"休息够了，回来先按『{next_step_text}』，把状态慢慢接回来。",
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
                "先暂停也可以。把这次停下的原因记住，等你回来我帮你重新接住节奏。",
                "先停一下没关系。回来时我们直接从最小下一步重新起。",
                "暂停不是掉线，等你回来我们就把节奏重新接起来。",
            ]
        if event_type == "session_paused_too_long":
            if recovery_state == "recovery_needed":
                return [
                    "你已经停了有一会儿。现在更像是需要恢复，先休息，不用硬把产出推出来。",
                    "停得久说明身体或心力可能在报警。今天先收住，之后只接一个更小入口。",
                    "这次先把恢复排在前面，先休息、喝水、离开题目，等稳一些再回来。",
                ]
            if strained:
                return [
                    f"你已经停了有一会儿。先别催自己，先按『{next_step_text}』把入口缩小。",
                    "停得久也没关系，先判断自己是不是还撑得住；不行就把目标降到更小。",
                    "如果现在还是低能量，我们只重启一小步；再吃力就直接好好收尾。",
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
            if mode == "recovery" or strained:
                return [
                    f"欢迎回来。先按『{next_step_text}』，不需要补偿式猛冲。",
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
            if recovery_state == "recovery_needed":
                return [
                    "今天先停在这里就可以。先恢复，再决定什么时候重新开始，不急着证明什么。",
                    "这轮先放下。现在更重要的是休息和稳定，学习之后只从很小的入口接回。",
                    "你先把自己照顾好，今天不用再逼产出；下一次我们只接最小动作。",
                ]
            if strained:
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
            f"我在。先按『{next_step_text}』继续，不急着一下子做很多。",
            "先别把目标放太大，只接眼前这一小步就好。",
            "我会陪你把节奏守住，先完成最清楚的下一步。",
        ]

    def _care_prefix(self, style: StudyResponseStyle, *, recovery_state: str) -> str:
        if recovery_state in {"low_energy", "overwhelmed", "anxious_or_stressed", "recovery_needed"} or style.care_style == "soft":
            return "先缓一点，"
        if style.care_style == "strict_care":
            return "先稳住节奏，"
        return ""

    def _correction_hint(self, style: StudyResponseStyle, *, recovery_state: str) -> str:
        if recovery_state in {"low_energy", "overwhelmed", "anxious_or_stressed", "recovery_needed"}:
            return "先把负担放轻，"
        if style.correction_style == "firm" or style.dominance_style == "high":
            return "先把注意力收回来，"
        if style.dominance_style == "low":
            return "慢慢来，"
        return ""

    def _praise_phrase(self, style: StudyResponseStyle, *, recovery_state: str) -> str:
        if recovery_state == "recovery_needed":
            return "这一步已经够了。"
        return {
            "restrained": "这段完成了。",
            "warm": "做得好，我看到了。",
            "possessive_lite": "很好，这一段你有稳稳跟上。",
        }.get(style.praise_style, "做得好，我看到了。")

    def _completion_praise(self, style: StudyResponseStyle, *, recovery_state: str) -> str:
        if recovery_state == "recovery_needed":
            return "已经够了，先休息。"
        if style.praise_style == "warm":
            return "很好，我为你高兴。"
        if style.praise_style == "possessive_lite":
            return "很好，这段你稳稳做完了。"
        return "完成了。"

    def _recent_repetition_count(self, event_type: str, recent_event_types: List[str]) -> int:
        count = 0
        for name in recent_event_types:
            if name == event_type:
                count += 1
            else:
                break
        return count

    def _style_effects(self, style: StudyResponseStyle, *, recovery_state: str) -> Dict[str, Any]:
        strained = recovery_state != "stable"
        return {
            "dominance_tone": "direct" if style.dominance_style == "high" and not strained else "measured",
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
            "correction_tone": "gentle_redirect" if strained or style.correction_style == "gentle" else "firm_redirect",
            "pressure_override": "softened_for_recovery" if strained else "style_default",
        }

    def _pressure_level(self, recovery_state: str, firm: bool) -> str:
        if recovery_state == "recovery_needed":
            return "recovery_first"
        if recovery_state in {"low_energy", "overwhelmed", "anxious_or_stressed"}:
            return "softened"
        return "firm" if firm else "normal"

    def _response_mode(self, recovery_state: str) -> str:
        return {
            "stable": "normal_b2",
            "low_energy": "re_entry_support",
            "overwhelmed": "stabilize_and_shrink",
            "anxious_or_stressed": "ground_and_shrink",
            "recovery_needed": "recover_before_output",
        }.get(recovery_state, "normal_b2")

    def _adapted_behavior_summary(self, recovery_state: str, next_step_category: str) -> str:
        return f"{self._response_mode(recovery_state)} -> {next_step_category}"

    def _interpret_recovery_state(
        self,
        *,
        session: Dict[str, Any],
        wellbeing: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        recent_responses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        energy = self._level(wellbeing.get("energy_level"))
        stress = self._level(wellbeing.get("stress_level"))
        body = self._level(wellbeing.get("body_state_level"))
        note = str(wellbeing.get("note", "") or "").lower()
        score = {"stable": 0, "low_energy": 0, "overwhelmed": 0, "anxious_or_stressed": 0, "recovery_needed": 0}
        reasons: List[str] = []
        rule_trace: List[Dict[str, Any]] = []
        recent_event_types = [str(item.get("event_type", "") or "") for item in recent_events[:8]]
        recent_response_types = [str(item.get("event_type", "") or "") for item in recent_responses[:5]]
        friction_flags = {
            "pause_count": sum(1 for name in recent_event_types if name == "session_paused"),
            "long_pause_count": sum(1 for name in recent_event_types if name == "session_paused_too_long"),
            "resume_count": sum(1 for name in recent_event_types if name == "session_resumed"),
            "incomplete_focus_cycles": sum(1 for i, name in enumerate(recent_event_types) if name == "session_paused" and "focus_completed" not in recent_event_types[: i + 1]),
            "abandoned_recently": str(session.get("status", "") or "") == "abandoned" or "session_abandoned" in recent_event_types,
            "repeated_low_energy_responses": sum(1 for name in recent_response_types if name == "low_energy_start"),
            "summary_suggests_recovery": any(fragment in str(session.get(key, "") or "").lower() for key in ("summary", "blockers", "next_step") for fragment in ("rest", "recover", "缓", "累", "焦虑", "stuck")),
        }

        def add(state: str, points: int, reason: str) -> None:
            score[state] += points
            reasons.append(reason)
            rule_trace.append({"state": state, "points": points, "reason": reason})

        if energy is not None and energy <= 2:
            add("low_energy", 3, f"energy_level={energy} suggests reduced capacity")
        if stress is not None and stress >= 4:
            add("anxious_or_stressed", 3, f"stress_level={stress} suggests strain")
        if body is not None and body <= 2:
            add("recovery_needed", 3, f"body_state_level={body} suggests recovery first")
        if any(word in note for word in ("焦虑", "panic", "anxious", "stress", "stressed", "紧张")):
            add("anxious_or_stressed", 2, "wellbeing note contains anxiety/stress wording")
        if any(word in note for word in ("累", "exhausted", "tired", "撑不住", "drained", "没劲")):
            add("low_energy", 2, "wellbeing note contains low-energy wording")
        if any(word in note for word in ("难受", "不舒服", "sick", "ill", "头痛", "recover", "休息", "撑不住")):
            add("recovery_needed", 2, "wellbeing note contains recovery wording")
        if str(session.get("mode", "") or "") == "recovery":
            add("low_energy", 1, "recovery mode biases toward lower-pressure support")
        if energy is not None and energy <= 2 and stress is not None and stress >= 4:
            add("recovery_needed", 2, "combined low energy and high stress suggest recovery may be needed")
        if friction_flags["long_pause_count"] >= 2:
            add("low_energy", 1, "multiple long pauses suggest re-entry friction")
        if friction_flags["long_pause_count"] >= 2:
            add("recovery_needed", 2, "multiple long pauses suggest recovery may be better than pushing")
        if friction_flags["pause_count"] >= 2 and friction_flags["resume_count"] <= 1:
            add("overwhelmed", 2, "repeated pauses with limited recovery suggest overload")
        if friction_flags["incomplete_focus_cycles"] >= 2:
            add("overwhelmed", 2, "repeated incomplete focus cycles suggest study-flow friction")
        if friction_flags["abandoned_recently"]:
            add("recovery_needed", 2, "recent abandonment suggests stepping back before pushing")
        if friction_flags["summary_suggests_recovery"]:
            add("recovery_needed", 1, "session summary/blockers mention recovery-oriented language")
        if friction_flags["repeated_low_energy_responses"] >= 2:
            add("recovery_needed", 1, "recent responses already had to reduce pressure repeatedly")

        state_order = ["recovery_needed", "overwhelmed", "anxious_or_stressed", "low_energy", "stable"]
        selected = "stable"
        if max(score.values()) > 0:
            selected = max(state_order, key=lambda item: (score[item], -state_order.index(item)))
        wellbeing_signal = {
            "energy_level": energy,
            "stress_level": stress,
            "body_state_level": body,
            "overwhelmed": any(score[name] > 0 for name in ("overwhelmed", "anxious_or_stressed", "recovery_needed", "low_energy")),
        }
        return {
            "state": selected,
            "score": score,
            "reasons": reasons[:6],
            "rule_trace": rule_trace[:8],
            "recent_friction_flags": friction_flags,
            "wellbeing_signal": wellbeing_signal,
        }

    def _select_next_step_category(
        self,
        *,
        recovery_state: str,
        event_type: str,
        session: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        friction_flags: Dict[str, Any],
    ) -> Dict[str, Any]:
        mode = str(session.get("mode", "focus") or "focus")
        if recovery_state == "recovery_needed":
            return {"category": "stop_and_recover", "label": "先停下恢复", "reason": "recovery_needed overrides push"}
        if recovery_state in {"overwhelmed", "anxious_or_stressed"}:
            if friction_flags.get("long_pause_count", 0) >= 1 or event_type in {"session_paused_too_long", "session_abandoned"}:
                return {"category": "take_short_break", "label": "先短休再决定", "reason": "strained state + pause friction"}
            return {"category": "do_one_tiny_next_action", "label": "只做一个最小动作", "reason": "strained state shrinks the next action"}
        if recovery_state == "low_energy":
            if mode == "review":
                return {"category": "switch_to_lighter_review_task", "label": "改做更轻的复盘", "reason": "low energy favors lighter review"}
            return {"category": "do_one_tiny_next_action", "label": "只做一个最小动作", "reason": "low energy favors re-entry over output"}
        if event_type == "break_completed" and mode != "review":
            return {"category": "continue_current_block", "label": "继续当前这一小段", "reason": "stable post-break continuation"}
        if mode == "review":
            return {"category": "switch_to_lighter_review_task", "label": "继续轻量复盘", "reason": "review mode keeps scope narrow"}
        return {"category": "continue_current_block", "label": "继续当前这一段", "reason": "stable state keeps normal flow"}

    def _level(self, value: Any) -> Optional[int]:
        if value in {None, ""}:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _should_be_firm(self, style: StudyResponseStyle, event_type: str, recovery_state: str) -> bool:
        if recovery_state != "stable":
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

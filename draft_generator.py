"""Action Draft Generator: turn a selected Growth Experiment into a production draft.

Does not re-plan experiments. Does not mutate App Store / ads / social.
Uses Growth Agent MCP as a knowledge provider when available.

Screenshot drafts accept optional user-provided images as first-class input.
When those images are absent, missingInputs must request them — do not invent
current screenshot content.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.tools.mcp import MCPClient

from analysis_schema import ActionDraft, DraftGeneratorOutput
from config import get_growth_mcp_settings, get_growth_md_text
from llm import build_model
from store_context import StoreListingContext, collect_store_listing_context

logger = logging.getLogger(__name__)

# Canonical missingInputs label when screenshot drafts lack user images.
USER_PROVIDED_SCREENSHOTS_MISSING = (
    "User-provided current App Store screenshots "
    "(positions 1–2 or equivalent image uploads)"
)

DRAFT_SYSTEM_PROMPT = """
You are the Indie Growth Agent Draft Generator.

You do NOT choose new Growth Experiments.
A human already selected one Growth Experiment. Your job is to turn that
selected experiment into a concrete production draft a human can execute
manually after approval.

Inputs you may use:
1) The selected Growth Experiment (title, hypothesis, why, action, metrics, playbook)
2) Analyzer Facts / Most Important Finding
3) GROWTH.md standing constraints (when present)
4) Growth Agent MCP playbooks / calculators (knowledge only)
5) Observed App Store / product context provided in the prompt
6) User-provided current App Store screenshot images (when present)

Hard rules:
- Do not invent a different experiment. Stay faithful to the selected one.
- Do not invent App Store screenshots, captions, UI screens, or features that
  are not present in the provided context / Facts / declared capabilities /
  user-provided images.
- KPI / metric numbers (critical):
  - Absolute counts, percentages, rates, and period labels used in the draft
    MUST be copied verbatim from ANALYZER FACTS, provided metrics, the selected
    experiment fields, or Most Important Finding in this prompt.
  - Do NOT recalculate, round creatively, reverse the sign, substitute a
    different period's number, or invent a conflicting figure (e.g. never write
    "67.2% decrease" when Facts say impressions are 5,192 / +72.4%).
  - If a KPI is not present in the provided Facts/metrics, omit the number or
    put the gap in missingInputs — do not fill from memory or playbooks.
- User psychology / pain points (critical):
  - Unverified claims about user mindset (e.g. "beginner wording drives away
    intermediate users", "fu calculation is the biggest pain point") must NOT
    be stated as Fact.
  - If you mention them at all, label explicitly as hypothesis / possibility /
    speculation — never as observed fact.
- Unverified performance / quality claims in copy (critical):
  - Ban unverified claims such as "in 5 seconds", "accurate", "strongest",
    "maximum / best" unless the exact claim is supported by measured Evidence
    or confirmed listing/screenshot text in this prompt.
  - Prefer concrete, observable phrasing grounded in visible creatives or Facts.
- Growth Playbook vs product Facts (critical):
  - Playbook principles are judgment aids only (general ASO / marketing advice).
  - Never present playbook guidance as if this product has already proven that
    effect. Separate "playbook suggests…" from "Facts for this product show…".
- Grounding for product capabilities (critical):
  - GA4 event names and event definitions describe WHEN an analytics event fires.
    They do NOT prove UI features such as "automatic totaling", "history review",
    "match replay", dashboards, or other screens.
  - Never expand an event definition into a product capability claim for copy,
    captions, or recommendedScreen unless that capability is visible in a
    user-provided screenshot or explicitly present in listing text provided.
  - App name / subtitle / listing text may ground messaging only about what they
    literally say (e.g. score calculation if present in the name).
  - If unsure whether a feature is shown, omit it; prefer narrower copy.
- For screenshot_copy drafts, current listing screenshots are expected as
  user-provided image inputs. If USER-PROVIDED SCREENSHOTS are missing, you
  MUST include that gap in missingInputs (use the exact provided label) and
  only draft message goals / copy alternatives that do not pretend to have
  seen the current creatives.
- When user-provided screenshots ARE present:
  - Ground recommendations in what those images actually show (visible UI,
    visible caption text, visible subject).
  - For each position fill currentMessage (what the current creative appears to
    communicate), keep (what to retain), change (what to change, or "none"),
    copyDraft (proposed caption/copy only if change is needed; else may be
    empty or "keep current"), recommendedScreen, why.
  - If the current screenshots already adequately serve the experiment objective
    (e.g. value is already clear for search users), set noChangeRecommended=true
    and explain in rationale/notes. Do NOT invent changes merely because Planner
    proposed a screenshot experiment.
- For recommendedScreen: if the exact screen is unknown, write
  "unknown — screen inventory not provided; human must pick an existing screen
  that shows <grounded capability>" — never invent a screen name as if confirmed.
- Obey GROWTH.md: budget ¥0, limited weekly time, no paid ASO tools, no auto
  publish, drafts are proposals for human approval only.
- Prefer Growth MCP growth_playbook for ASO / screenshot guidance when drafting
  screenshot_copy drafts (as general guidance only — see Playbook vs Facts rule).
- Never claim to have changed or published anything.
- Draft type should reflect the selected experiment
  (e.g. screenshot_copy for screenshot messaging work; measurement_plan for
  monitoring-only experiments). Do not force screenshots for non-screenshot work.
"""

DRAFT_STRUCTURED_PROMPT = """
Fill DraftGeneratorOutput.draft (ActionDraft).

Required:
- experimentTitle: copy from the selected experiment title
- draftType: e.g. screenshot_copy | measurement_plan | metadata | generic
- objective, rationale
- noChangeRecommended: true if current user-provided creatives already meet the
  objective; false otherwise. When true, keep change fields minimal / "none".
- screenshots: for screenshot_copy, usually positions 1–2 (or fewer if unsupported).
  Each item: position, messageGoal (optional), currentMessage, keep, change,
  copyDraft, recommendedScreen, why.
  Empty list when draftType is not screenshot-oriented.
- missingInputs: every material gap. For screenshot drafts without user-provided
  images, include the exact user-provided screenshots missing label from the prompt.
- notes: practical human next steps; remind that nothing is auto-published.
  Do not introduce KPI numbers absent from ANALYZER FACTS / metrics.
  Label unverified user-psychology claims as hypothesis/possibility if used.
  Keep playbook advice distinct from product Facts.
- playbooksUsed: Growth MCP playbook ids/titles actually used (may be empty)

Language: follow RESPONSE LANGUAGE for all prose fields.
"""


def _normalize_language(language: str | None) -> str:
    if language and language.lower().startswith("ja"):
        return "ja"
    return "en"


def _language_instruction(language: str) -> str:
    if language == "ja":
        return """

RESPONSE LANGUAGE: Japanese (ja)
Write draft prose in natural Japanese. Keep service / metric identifiers unchanged.
"""
    return """

RESPONSE LANGUAGE: English (en)
Write draft prose in clear English. Keep service / metric identifiers unchanged.
"""


def _create_mcp_client() -> MCPClient | None:
    settings = get_growth_mcp_settings()
    if settings is None:
        return None
    params = StdioServerParameters(
        command=settings.command,
        args=list(settings.args),
        cwd=settings.cwd,
    )
    return MCPClient(lambda: stdio_client(params), prefix="growth")


def _exp_get(experiment: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in experiment and experiment[key] is not None:
            return experiment[key]
    return None


def _experiment_block(experiment: dict[str, Any]) -> str:
    fields = [
        ("title", _exp_get(experiment, "title")),
        ("hypothesis", _exp_get(experiment, "hypothesis")),
        ("why", _exp_get(experiment, "why")),
        ("action", _exp_get(experiment, "action")),
        (
            "targetMetric",
            _exp_get(experiment, "targetMetric", "target_metric"),
        ),
        (
            "expectedSignal",
            _exp_get(experiment, "expectedSignal", "expected_signal"),
        ),
        (
            "suggestedDuration",
            _exp_get(experiment, "suggestedDuration", "suggested_duration"),
        ),
        ("evidence", _exp_get(experiment, "evidence")),
        (
            "playbookReference",
            _exp_get(experiment, "playbookReference", "playbook_reference"),
        ),
    ]
    lines = ["SELECTED GROWTH EXPERIMENT (do not replace with a new experiment):"]
    for label, value in fields:
        lines.append(f"- {label}: {value if value is not None else ''}")
    return "\n".join(lines)


def looks_like_screenshot_experiment(experiment: dict[str, Any]) -> bool:
    """Heuristic: screenshot drafts expect user-provided listing images."""
    blob = " ".join(
        str(_exp_get(experiment, key) or "")
        for key in (
            "title",
            "action",
            "hypothesis",
            "why",
            "playbookReference",
            "playbook_reference",
        )
    ).lower()
    keywords = (
        "screenshot",
        "スクリーンショット",
        "visual asset",
        "スクショ",
        "サムネ",
    )
    return any(k.lower() in blob for k in keywords)


def _normalize_user_screenshots(
    raw: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Keep only usable user screenshot payloads (metadata and/or image bytes)."""
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(raw or []):
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        try:
            position_int = int(position) if position is not None else index + 1
        except (TypeError, ValueError):
            position_int = index + 1
        file_name = str(item.get("fileName") or item.get("file_name") or "").strip()
        mime = str(item.get("mimeType") or item.get("mime_type") or "").strip()
        description = str(item.get("description") or "").strip()
        data_b64 = str(item.get("dataBase64") or item.get("data_base64") or "").strip()
        if data_b64.startswith("data:") and "," in data_b64:
            header, data_b64 = data_b64.split(",", 1)
            if not mime and ";" in header:
                mime = header[5:].split(";", 1)[0]
        has_image = bool(data_b64)
        has_meta = bool(file_name or description)
        if not has_image and not has_meta:
            continue
        entry: dict[str, Any] = {
            "position": position_int,
            "fileName": file_name or None,
            "mimeType": mime or None,
            "description": description or None,
            "hasImageBytes": has_image,
        }
        if has_image:
            entry["dataBase64"] = data_b64
        cleaned.append(entry)
    cleaned.sort(key=lambda x: x["position"])
    return cleaned


def _user_screenshots_prompt_block(screenshots: list[dict[str, Any]]) -> list[str]:
    if not screenshots:
        return [
            "USER-PROVIDED SCREENSHOTS: (none)",
            "If this is a screenshot_copy draft, missingInputs MUST include:",
            f"  {USER_PROVIDED_SCREENSHOTS_MISSING}",
            "Do not invent what the current App Store screenshots look like.",
            "",
        ]
    lines = [
        "USER-PROVIDED SCREENSHOTS (first-class input — ground the draft in these):",
    ]
    for item in screenshots:
        bits = [f"position={item['position']}"]
        if item.get("fileName"):
            bits.append(f"fileName={item['fileName']}")
        if item.get("mimeType"):
            bits.append(f"mimeType={item['mimeType']}")
        if item.get("hasImageBytes"):
            bits.append("imageBytes=attached")
        else:
            bits.append("imageBytes=not attached (metadata/description only)")
        lines.append("- " + ", ".join(bits))
        if item.get("description"):
            lines.append(f"  description: {item['description']}")
    lines.append(
        "Use attached images when present. Still list other gaps in missingInputs."
    )
    lines.append("")
    return lines


def _image_format(mime: str | None, file_name: str | None) -> str:
    mime = (mime or "").lower()
    name = (file_name or "").lower()
    if "jpeg" in mime or "jpg" in mime or name.endswith(".jpg") or name.endswith(".jpeg"):
        return "jpeg"
    if "webp" in mime or name.endswith(".webp"):
        return "webp"
    if "gif" in mime or name.endswith(".gif"):
        return "gif"
    return "png"


def _build_agent_prompt(
    text_prompt: str,
    user_screenshots: list[dict[str, Any]],
) -> str | list[dict[str, Any]]:
    """Attach user screenshot bytes as multimodal content when available."""
    image_blocks: list[dict[str, Any]] = []
    for item in user_screenshots:
        raw_b64 = item.get("dataBase64")
        if not raw_b64:
            continue
        try:
            data = base64.b64decode(raw_b64, validate=False)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Skipping invalid base64 for user screenshot position=%s",
                item.get("position"),
            )
            continue
        if not data:
            continue
        image_blocks.append(
            {
                "image": {
                    "format": _image_format(
                        item.get("mimeType"),
                        item.get("fileName"),
                    ),
                    "source": {"bytes": data},
                }
            }
        )
        caption = (
            f"User-provided App Store screenshot position {item.get('position')}"
        )
        if item.get("fileName"):
            caption += f" ({item['fileName']})"
        image_blocks.append({"text": caption})

    if not image_blocks:
        return text_prompt
    return [{"text": text_prompt}, *image_blocks]


def _period_metrics_prompt_block(
    period: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    *,
    analysis_run_id: str | None,
    data_source: str | None,
) -> list[str]:
    lines = [
        "ANALYSIS CONTEXT (same Analyze run as the selected experiment):",
        f"- analysisRunId: {analysis_run_id or '(none)'}",
        f"- dataSource: {data_source or '(unspecified)'}",
    ]
    period = period or {}
    if period:
        lines.extend(
            [
                f"- period.start: {period.get('start')}",
                f"- period.end: {period.get('end')}",
                f"- period.label: {period.get('label')}",
                f"- period.comparisonLabel: {period.get('comparisonLabel')}",
                f"- period.lookbackDays: {period.get('lookbackDays')}",
            ]
        )
    else:
        lines.append("- period: (not provided)")

    metrics = metrics or {}
    if metrics:
        lines.append("- metrics (use only these observed values; do not recalculate):")
        for key in ("appStore", "ga4", "admob", "app_store"):
            group = metrics.get(key)
            if not isinstance(group, dict):
                continue
            lines.append(
                f"  [{key}] connected={group.get('connected')} "
                f"title={group.get('title') or group.get('id')}"
            )
            for item in group.get("metrics") or []:
                if not isinstance(item, dict):
                    continue
                bits = [f"id={item.get('id')}"]
                if item.get("absolute") is not None:
                    bits.append(f"absolute={item.get('absolute')}")
                if item.get("value") is not None:
                    bits.append(f"value={item.get('value')}")
                if item.get("changePercent") is not None:
                    bits.append(f"changePercent={item.get('changePercent')}")
                lines.append("    - " + ", ".join(bits))
    else:
        lines.append("- metrics: (not provided)")
    lines.append("")
    return lines


def build_draft_prompt(
    *,
    experiment: dict[str, Any],
    most_important_finding: str,
    facts: list[str],
    playbooks_consulted: list[str],
    growth_md: str | None,
    store: StoreListingContext,
    user_screenshots: list[dict[str, Any]] | None = None,
    period: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    analysis_run_id: str | None = None,
    data_source: str | None = None,
) -> str:
    if growth_md:
        growth_block = [
            "GROWTH.md (standing constraints — MUST obey):",
            growth_md.strip(),
            "",
        ]
    else:
        growth_block = ["GROWTH.md: (not provided)", ""]

    playbook_lines = (
        [f"- {item}" for item in playbooks_consulted]
        if playbooks_consulted
        else ["- (none)"]
    )
    fact_lines = [f"- {item}" for item in facts] if facts else ["- (none)"]
    shots = list(user_screenshots or [])

    parts = [
        "DRAFT GENERATOR INPUT",
        "",
        *growth_block,
        *_period_metrics_prompt_block(
            period,
            metrics,
            analysis_run_id=analysis_run_id,
            data_source=data_source,
        ),
        _experiment_block(experiment),
        "",
        "PLANNER PLAYBOOKS CONSULTED (context):",
        *playbook_lines,
        "",
        "ANALYZER MOST IMPORTANT FINDING:",
        most_important_finding or "(empty)",
        "",
        "ANALYZER FACTS:",
        *fact_lines,
        "",
        store.to_prompt_block(),
        "",
        *_user_screenshots_prompt_block(shots),
        "TASK:",
        "1) If helpful, call growth_playbook for ASO / screenshot guidance relevant",
        "   to THIS selected experiment (do not pick a new experiment).",
        "   Treat playbook text as general guidance only — never as proven results",
        "   for this product.",
        "2) Produce a human-executable draft. Prefer screenshot_copy when the",
        "   selected experiment is about screenshot / visual asset messaging.",
        "3) KPI numbers in objective/rationale/notes/copy MUST come only from",
        "   ANALYZER FACTS / metrics / experiment fields / ANALYSIS CONTEXT above.",
        "   Do not invent or swap conflicting figures.",
        "4) Put every unavailable listing/screen inventory item into missingInputs.",
        "   If user-provided screenshots are missing for a screenshot draft, include:",
        f"   {USER_PROVIDED_SCREENSHOTS_MISSING}",
        "5) Fill DraftGeneratorOutput.",
    ]
    return "\n".join(parts)


def _draft_to_api_dict(draft: ActionDraft) -> dict[str, Any]:
    return {
        "experimentTitle": draft.experiment_title,
        "draftType": draft.draft_type,
        "objective": draft.objective,
        "rationale": draft.rationale,
        "noChangeRecommended": bool(draft.no_change_recommended),
        "screenshots": [
            {
                "position": item.position,
                "messageGoal": item.message_goal,
                "currentMessage": item.current_message,
                "keep": item.keep,
                "change": item.change,
                "copyDraft": item.copy_draft,
                "recommendedScreen": item.recommended_screen,
                "why": item.why,
            }
            for item in (draft.screenshots or [])
        ],
        "missingInputs": list(draft.missing_inputs or []),
        "notes": draft.notes or "",
        "playbooksUsed": list(draft.playbooks_used or []),
    }


def _ensure_user_screenshot_missing(
    missing: list[str],
    *,
    experiment: dict[str, Any],
    draft_type: str,
    user_screenshots: list[dict[str, Any]],
) -> list[str]:
    needs_shots = looks_like_screenshot_experiment(experiment) or (
        "screenshot" in (draft_type or "").lower()
    )
    if needs_shots and not user_screenshots:
        if USER_PROVIDED_SCREENSHOTS_MISSING not in missing:
            missing = [USER_PROVIDED_SCREENSHOTS_MISSING, *missing]
        legacy = "Current App Store screenshots (image content / captions)"
        missing = [m for m in missing if m != legacy]
    return missing


def run_draft_generator(
    *,
    experiment: dict[str, Any],
    most_important_finding: str = "",
    facts: list[str] | None = None,
    playbooks_consulted: list[str] | None = None,
    app: dict[str, Any] | None = None,
    user_screenshots: list[dict[str, Any]] | None = None,
    language: str | None = "ja",
    period: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    analysis_run_id: str | None = None,
    data_source: str | None = None,
) -> dict[str, Any]:
    """Generate a production draft for one human-selected experiment.

    ``user_screenshots`` is optional first-class input for screenshot drafts:
    each item may include position, fileName, mimeType, description, dataBase64.
    When absent on a screenshot experiment, missingInputs requests the upload.

    Returns an API-shaped dict. Raises on hard failure (caller maps to HTTP).
    """
    lang = _normalize_language(language)
    facts = list(facts or [])
    playbooks_consulted = list(playbooks_consulted or [])
    shots = _normalize_user_screenshots(user_screenshots)
    growth_md = get_growth_md_text()
    store = collect_store_listing_context(app_hint=app or {})
    run_id = analysis_run_id or experiment.get("analysisRunId") or experiment.get(
        "analysis_run_id"
    )

    text_prompt = build_draft_prompt(
        experiment=experiment,
        most_important_finding=most_important_finding,
        facts=facts,
        playbooks_consulted=playbooks_consulted,
        growth_md=growth_md,
        store=store,
        user_screenshots=shots,
        period=period,
        metrics=metrics,
        analysis_run_id=run_id,
        data_source=data_source,
    ) + _language_instruction(lang)
    agent_prompt = _build_agent_prompt(text_prompt, shots)

    logger.info(
        "Running Draft Generator language=%s experiment=%s growth_md=%s "
        "user_screenshots=%s with_bytes=%s analysisRunId=%s dataSource=%s "
        "period=%s→%s",
        lang,
        (experiment.get("title") or "")[:80],
        "yes" if growth_md else "no",
        len(shots),
        sum(1 for s in shots if s.get("hasImageBytes")),
        run_id,
        data_source,
        (period or {}).get("start"),
        (period or {}).get("end"),
    )

    mcp_client = _create_mcp_client()
    if mcp_client is not None:
        with mcp_client:
            tools = list(mcp_client.list_tools_sync())
            agent = Agent(
                system_prompt=DRAFT_SYSTEM_PROMPT, tools=tools, model=build_model()
            )
            result = agent(
                agent_prompt,
                structured_output_model=DraftGeneratorOutput,
                structured_output_prompt=DRAFT_STRUCTURED_PROMPT,
            )
    else:
        logger.info("Growth MCP not configured; Draft Generator runs without tools")
        agent = Agent(system_prompt=DRAFT_SYSTEM_PROMPT, tools=[], model=build_model())
        result = agent(
            agent_prompt,
            structured_output_model=DraftGeneratorOutput,
            structured_output_prompt=DRAFT_STRUCTURED_PROMPT,
        )

    structured = result.structured_output
    if structured is None or structured.draft is None:
        raise RuntimeError("Draft Generator returned no structured draft")

    draft = structured.draft
    missing = list(draft.missing_inputs or [])
    for item in store.missing_inputs:
        if item not in missing:
            missing.append(item)
    missing = _ensure_user_screenshot_missing(
        missing,
        experiment=experiment,
        draft_type=draft.draft_type,
        user_screenshots=shots,
    )
    draft = draft.model_copy(update={"missing_inputs": missing})

    return {
        "draft": _draft_to_api_dict(draft),
        "analysisRunId": run_id,
        "dataSource": data_source,
        "period": period or {},
        "storeContext": {
            "available": store.available,
            "missingInputs": store.missing_inputs,
            "notes": store.notes,
        },
        "userScreenshotsReceived": [
            {
                "position": s["position"],
                "fileName": s.get("fileName"),
                "mimeType": s.get("mimeType"),
                "hasImageBytes": bool(s.get("hasImageBytes")),
                "description": s.get("description"),
            }
            for s in shots
        ],
    }

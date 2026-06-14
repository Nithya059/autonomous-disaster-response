import json
import logging
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.state import GraphState
from app.models.incident import Incident
from app.schemas.websocket import WsMessage
from app.logging_config import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

AGENT_NAME = "verification"

# Confidence scoring weights
SOURCE_WEIGHT = 0.4
SEVERITY_CONSISTENCY_WEIGHT = 0.3
LLM_WEIGHT = 0.3

SEVERITY_SCORES = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}


def _rule_based_confidence(incident: dict) -> float:
    """
    Compute a deterministic confidence score based on:
    - Source credibility (gdacs > weather_api > social > unknown)
    - Severity plausibility vs incident type
    Returns a float 0.0–1.0.
    """
    source = (incident.get("source") or "").lower()
    severity = incident.get("severity", "low")
    inc_type = incident.get("type", "other")

    # Source credibility
    if "gdacs" in source:
        source_score = 1.0
    elif "openweather" in source or "weather" in source:
        source_score = 0.8
    elif "mock" in source or "seed" in source:
        source_score = 0.7
    else:
        source_score = 0.4

    # Severity vs type plausibility
    plausible_combos = {
        "flood": {"medium", "high", "critical"},
        "earthquake": {"high", "critical"},
        "fire": {"medium", "high", "critical"},
        "storm": {"medium", "high", "critical"},
        "other": {"low", "medium", "high", "critical"},
    }
    severity_score = 0.8 if severity in plausible_combos.get(inc_type, set()) else 0.4

    return round(
        (source_score * SOURCE_WEIGHT) + (severity_score * SEVERITY_CONSISTENCY_WEIGHT),
        3,
    )


async def _llm_confidence(incident: dict, run_id: str) -> float:
    """
    Ask the LLM to assess incident credibility.
    Returns a float 0.0–1.0 or 0.5 as fallback if LLM is unavailable.
    """
    if not settings.openai_api_key:
        return 0.5

    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.openai_api_key,
            max_tokens=50,
        )
        prompt = (
            f"Rate the credibility of this disaster incident report from 0.0 to 1.0.\n"
            f"Incident: {incident['title']}\n"
            f"Type: {incident['type']}, Severity: {incident['severity']}, "
            f"Source: {incident.get('source', 'unknown')}\n"
            f"Respond with ONLY a decimal number between 0.0 and 1.0."
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        score = float(response.content.strip())
        return max(0.0, min(1.0, score))
    except Exception as exc:
        logger.warning("[%s] LLM confidence check failed: %s", AGENT_NAME, exc)
        return 0.5


async def verification_agent(state: GraphState) -> GraphState:
    """
    LangGraph node: Verification Agent.

    Responsibilities:
      1. Apply rule-based confidence scoring to each raw incident.
      2. Use LLM to augment confidence score when API key is available.
      3. Combine scores into a final confidence value (0.0–1.0).
      4. Persist updated confidence to database.
      5. Populate state["verified"] for the prioritization agent.
    """
    run_id = state["run_id"]
    db = state["db_session"]
    trace: list[dict] = state["agent_trace"]
    raw_incidents = state["raw_incidents"]

    from app.services.websocket_manager import manager

    def _emit(step: str, message: str, severity="info", payload=None):
        msg = WsMessage.agent_event(
            agent=AGENT_NAME,
            step=step,
            message=message,
            run_id=run_id,
            severity=severity,
            payload=payload,
        )
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(msg.to_json()))
        except RuntimeError:
            pass

        trace.append({
            "agent_name": AGENT_NAME,
            "step": step,
            "message": message,
            "severity": severity,
            "payload_json": json.dumps(payload) if payload else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
        })
        logger.info("[%s] %s — %s", AGENT_NAME, step, message)

    _emit("start", f"Verification agent started. Processing {len(raw_incidents)} incidents.")

    if not raw_incidents:
        _emit("skip", "No incidents to verify.", severity="warning")
        return {**state, "verified": [], "agent_trace": trace}

    verified = []

    for incident in raw_incidents:
        inc_id = incident.get("id")
        title = incident.get("title", "Unknown")

        _emit("scoring", f"Scoring incident: {title}")

        # Rule-based component
        rule_score = _rule_based_confidence(incident)

        # LLM component
        llm_score = await _llm_confidence(incident, run_id)

        # Combined confidence
        final_confidence = round(
            rule_score + (llm_score * LLM_WEIGHT),
            3,
        )
        final_confidence = max(0.0, min(1.0, final_confidence))

        _emit(
            "scored",
            f"'{title}' confidence={final_confidence:.2f} "
            f"(rule={rule_score:.2f}, llm={llm_score:.2f})",
            payload={
                "incident_id": inc_id,
                "confidence": final_confidence,
                "rule_score": rule_score,
                "llm_score": llm_score,
            },
        )

        # Persist confidence to DB
        if inc_id:
            try:
                db_inc = db.query(Incident).filter(Incident.id == inc_id).first()
                if db_inc:
                    db_inc.confidence = final_confidence
                    db_inc.status = "verified"
                    db.flush()
            except Exception as exc:
                logger.warning("[%s] Failed to update incident %s: %s", AGENT_NAME, inc_id, exc)

        verified_incident = {
            **incident,
            "confidence": final_confidence,
            "status": "verified",
        }
        verified.append(verified_incident)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        _emit("db_error", f"Failed to persist confidence scores: {exc}", severity="error")

    _emit(
        "complete",
        f"Verification complete. {len(verified)} incidents scored.",
        severity="success",
        payload={"verified_count": len(verified)},
    )

    return {**state, "verified": verified, "agent_trace": trace}

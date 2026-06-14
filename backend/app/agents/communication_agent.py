import json
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agents.state import GraphState
from app.models.agent_log import AgentLog
from app.schemas.websocket import WsMessage
from app.logging_config import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

AGENT_NAME = "communication"

ALERT_CHANNELS = ["dashboard", "sms_gateway", "email_list"]


async def _compose_alert(allocation: dict, use_llm: bool) -> str:
    """
    Compose a human-readable alert message for an allocation.
    Uses LLM when available, falls back to template.
    """
    if use_llm and settings.openai_api_key:
        try:
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=settings.openai_api_key,
                max_tokens=120,
            )
            prompt = (
                f"Write a concise emergency dispatch alert (max 2 sentences) for:\n"
                f"Incident: {allocation['incident_title']}\n"
                f"Resource dispatched: {allocation['resource_name']} "
                f"({allocation['resource_type']})\n"
                f"Distance: {allocation['distance_km']}km\n"
                f"Be direct and professional. No preamble."
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as exc:
            logger.warning("[%s] LLM alert composition failed: %s", AGENT_NAME, exc)

    # Fallback template
    return (
        f"DISPATCH ALERT: {allocation['resource_name']} ({allocation['resource_type']}) "
        f"has been dispatched to incident '{allocation['incident_title']}' "
        f"located {allocation['distance_km']}km away. Immediate response required."
    )


async def communication_agent(state: GraphState) -> GraphState:
    """
    LangGraph node: Communication Agent.

    Responsibilities:
      1. For each allocation, compose a human-readable alert message.
      2. Simulate dispatch to alert channels (dashboard, SMS, email).
      3. Persist all agent_trace entries to the agent_logs table.
      4. Broadcast final run summary via WebSocket.
      5. Populate state["alerts"] with sent alert records.
    """
    run_id = state["run_id"]
    db = state["db_session"]
    trace: list[dict] = state["agent_trace"]
    allocations = state["allocations"]

    from app.services.websocket_manager import manager

    use_llm = bool(settings.openai_api_key)

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

    _emit(
        "start",
        f"Communication agent started. Composing alerts for {len(allocations)} allocations.",
    )

    alerts = []

    for allocation in allocations:
        alert_text = await _compose_alert(allocation, use_llm=use_llm)
        sent_at = datetime.now(timezone.utc).isoformat()

        alert = {
            "incident_id": allocation["incident_id"],
            "incident_title": allocation["incident_title"],
            "resource_id": allocation["resource_id"],
            "resource_name": allocation["resource_name"],
            "message": alert_text,
            "channels": ALERT_CHANNELS,
            "sent_at": sent_at,
        }
        alerts.append(alert)

        # Broadcast alert_sent event to all WebSocket clients
        alert_msg = WsMessage.alert_sent(
            run_id=run_id,
            payload=alert,
            message=alert_text,
        )
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(alert_msg.to_json()))
        except RuntimeError:
            pass

        _emit(
            "alert_dispatched",
            f"Alert sent for '{allocation['incident_title']}' via {len(ALERT_CHANNELS)} channels",
            severity="success",
            payload=alert,
        )

    # ------------------------------------------------------------------
    # Persist entire agent_trace to agent_logs table
    # ------------------------------------------------------------------
    _emit("persisting_logs", f"Persisting {len(trace)} agent log entries to database.")

    try:
        for entry in trace:
            log = AgentLog(
                agent_name=entry["agent_name"],
                step=entry["step"],
                message=entry["message"],
                severity=entry["severity"],
                payload_json=entry.get("payload_json"),
                run_id=entry["run_id"],
            )
            db.add(log)
        db.commit()
        _emit("logs_persisted", "All agent logs committed to database.", severity="success")
    except Exception as exc:
        db.rollback()
        _emit("log_error", f"Failed to persist agent logs: {exc}", severity="error")
        logger.error("[%s] Log persistence failed: %s", AGENT_NAME, exc)

    # ------------------------------------------------------------------
    # Broadcast run summary
    # ------------------------------------------------------------------
    summary = WsMessage.system_status(
        message=(
            f"Pipeline run {run_id[:8]}... complete. "
            f"{len(state.get('raw_incidents', []))} incidents processed, "
            f"{len(allocations)} resources dispatched, "
            f"{len(alerts)} alerts sent."
        ),
        payload={
            "run_id": run_id,
            "incidents_processed": len(state.get("raw_incidents", [])),
            "allocations": len(allocations),
            "alerts_sent": len(alerts),
        },
    )
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast(summary.to_json()))
    except RuntimeError:
        pass

    _emit(
        "complete",
        f"Communication agent complete. {len(alerts)} alerts dispatched.",
        severity="success",
        payload={"alert_count": len(alerts)},
    )

    return {**state, "alerts": alerts, "agent_trace": trace}

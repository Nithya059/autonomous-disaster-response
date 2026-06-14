from typing import Any, TypedDict


class GraphState(TypedDict):
    """
    Shared state passed between all LangGraph agent nodes.
    Each node receives this dict, mutates its relevant fields,
    and returns the updated dict for the next node.

    Field ownership by agent:
      ingestion_agent      → populates raw_incidents
      verification_agent   → populates verified (from raw_incidents)
      prioritization_agent → populates prioritized (from verified)
      allocation_agent     → populates allocations (from prioritized)
      communication_agent  → populates alerts (from allocations)
      all agents           → append to agent_trace
    """

    # Unique identifier for this full pipeline execution (UUID string).
    # Set by the scheduler or /agents/run endpoint before graph invocation.
    run_id: str

    # Raw incident dicts fetched/normalized by the ingestion agent.
    # Each dict conforms to IncidentCreate field names plus an optional
    # `external_id` for deduplication.
    raw_incidents: list[dict]

    # Incidents after cross-source verification with confidence scores attached.
    # Each dict is an IncidentRead-compatible shape with `confidence` populated.
    verified: list[dict]

    # Incidents after severity × population × resource-gap scoring.
    # Each dict adds a `priority_score` float field.
    prioritized: list[dict]

    # Allocation decisions produced by the allocation agent.
    # Each dict: { incident_id, resource_id, resource_name, distance_km }
    allocations: list[dict]

    # Outbound alert payloads produced by the communication agent.
    # Each dict: { incident_id, message, channels, sent_at }
    alerts: list[dict]

    # Append-only trace of all agent events during this run.
    # Each entry mirrors AgentLogRead field names so it can be persisted
    # directly to the agent_logs table and broadcast as WsMessage.
    # Shape: { agent_name, step, message, severity, payload_json, timestamp, run_id }
    agent_trace: list[dict]

    # SQLAlchemy Session passed through the graph so agents can persist
    # data without managing their own sessions.
    # Typed as Any to avoid circular imports with app.database.
    db_session: Any

"""
External data ingestion service.
Fetches disaster incidents from GDACS RSS and OpenWeatherMap APIs.
Falls back to mock_data.py when API keys are absent or requests fail.
"""

import json
import xml.etree.ElementTree as ET
from typing import List

import httpx

from app.config import get_settings
from app.logging_config import get_logger
from app.services.mock_data import get_mock_incidents

logger = get_logger(__name__)
settings = get_settings()

# GDACS RSS namespaces
GDACS_NS = {
    "gdacs": "http://www.gdacs.org",
    "geo":   "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "dc":    "http://purl.org/dc/elements/1.1/",
}

GDACS_SEVERITY_MAP = {
    "Green":  "low",
    "Orange": "medium",
    "Red":    "critical",
}

GDACS_TYPE_MAP = {
    "FL": "flood",
    "EQ": "earthquake",
    "TC": "storm",   # Tropical Cyclone
    "WF": "fire",    # Wildfire
    "VO": "other",   # Volcano
    "TS": "storm",   # Tsunami
    "DR": "other",   # Drought
}


async def _fetch_gdacs() -> List[dict]:
    """Fetch and parse GDACS RSS feed into normalized incident dicts."""
    incidents = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.gdacs_api_url)
            response.raise_for_status()

        root = ET.fromstring(response.text)
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            try:
                title_el = item.find("title")
                title = title_el.text.strip() if title_el is not None else "Unknown event"

                # GDACS alert level → severity
                alert_el = item.find("gdacs:alertlevel", GDACS_NS)
                severity = GDACS_SEVERITY_MAP.get(
                    alert_el.text.strip() if alert_el is not None else "", "medium"
                )

                # Event type
                type_el = item.find("gdacs:eventtype", GDACS_NS)
                event_type_code = type_el.text.strip() if type_el is not None else "FL"
                incident_type = GDACS_TYPE_MAP.get(event_type_code, "other")

                # Coordinates
                lat_el = item.find("geo:lat", GDACS_NS)
                lng_el = item.find("geo:long", GDACS_NS)
                lat = float(lat_el.text.strip()) if lat_el is not None else 0.0
                lng = float(lng_el.text.strip()) if lng_el is not None else 0.0

                # External ID for deduplication
                guid_el = item.find("guid")
                external_id = guid_el.text.strip() if guid_el is not None else title

                incidents.append({
                    "external_id": external_id,
                    "title": title[:500],
                    "type": incident_type,
                    "severity": severity,
                    "lat": lat,
                    "lng": lng,
                    "source": "gdacs",
                    "raw_data": json.dumps({"guid": external_id, "title": title}),
                })
            except Exception as exc:
                logger.warning("Failed to parse GDACS item: %s", exc)
                continue

        logger.info("GDACS: parsed %d incidents", len(incidents))
    except Exception as exc:
        logger.warning("GDACS fetch failed: %s", exc)

    return incidents


async def _fetch_openweather() -> List[dict]:
    """
    Fetch severe weather alerts from OpenWeatherMap.
    Returns empty list if API key is absent.
    """
    if not settings.openweather_api_key:
        return []

    incidents = []
    # Bounding box for Southeast Asia
    bbox_centers = [
        ("Manila",    14.5995, 120.9842),
        ("Cebu",      10.3157, 123.8854),
        ("Davao",      7.1907, 125.4553),
        ("Bangkok",   13.7563, 100.5018),
        ("Jakarta",   -6.2088, 106.8456),
    ]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for city_name, lat, lng in bbox_centers:
                url = (
                    f"https://api.openweathermap.org/data/3.0/onecall"
                    f"?lat={lat}&lon={lng}&exclude=current,minutely,hourly,daily"
                    f"&appid={settings.openweather_api_key}"
                )
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    alerts = data.get("alerts", [])

                    for alert in alerts:
                        event = alert.get("event", "Weather Alert")
                        description = alert.get("description", "")
                        severity = "medium"
                        desc_lower = description.lower()
                        if any(w in desc_lower for w in ["extreme", "severe", "emergency"]):
                            severity = "critical"
                        elif any(w in desc_lower for w in ["warning", "danger"]):
                            severity = "high"

                        incidents.append({
                            "external_id": f"ow-{city_name}-{alert.get('start', '')}",
                            "title": f"{event} near {city_name}",
                            "type": "storm",
                            "severity": severity,
                            "lat": lat,
                            "lng": lng,
                            "source": "openweather",
                            "raw_data": json.dumps({"event": event, "city": city_name}),
                        })
                except Exception as exc:
                    logger.warning("OpenWeather fetch failed for %s: %s", city_name, exc)

    except Exception as exc:
        logger.warning("OpenWeather client error: %s", exc)

    logger.info("OpenWeather: parsed %d alerts", len(incidents))
    return incidents


async def fetch_incidents() -> List[dict]:
    """
    Main entry point for the ingestion agent.

    Attempts to fetch from GDACS and OpenWeatherMap in parallel.
    Falls back to mock_data if both fail or keys are absent.
    Returns a combined, deduplicated list of normalized incident dicts.
    """
    import asyncio

    gdacs_task = asyncio.create_task(_fetch_gdacs())
    weather_task = asyncio.create_task(_fetch_openweather())

    gdacs_results, weather_results = await asyncio.gather(
        gdacs_task, weather_task, return_exceptions=True
    )

    combined: List[dict] = []

    if isinstance(gdacs_results, list):
        combined.extend(gdacs_results)
    else:
        logger.warning("GDACS task error: %s", gdacs_results)

    if isinstance(weather_results, list):
        combined.extend(weather_results)
    else:
        logger.warning("OpenWeather task error: %s", weather_results)

    # Fall back to mock data if nothing was fetched
    if not combined:
        logger.info("No external data fetched — using mock data fallback")
        combined = get_mock_incidents()

    # Deduplicate by external_id
    seen_ids: set = set()
    unique: List[dict] = []
    for inc in combined:
        ext_id = inc.get("external_id", inc.get("title", ""))
        if ext_id not in seen_ids:
            seen_ids.add(ext_id)
            unique.append(inc)

    logger.info("fetch_incidents: returning %d unique incidents", len(unique))
    return unique

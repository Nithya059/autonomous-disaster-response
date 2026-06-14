"""
Deterministic seed data for the Autonomous Disaster Response system.
Used when external APIs are unavailable or keys are absent.
Provides 8 realistic incidents and 12 resources across Southeast Asia.
"""

from typing import List


def get_mock_incidents() -> List[dict]:
    """
    Return 8 realistic disaster incidents across Southeast Asia.
    Each dict conforms to IncidentCreate field names plus `external_id`
    for deduplication in the ingestion agent.
    """
    return [
        {
            "external_id": "mock-inc-001",
            "title": "Severe flooding in Manila lowlands",
            "type": "flood",
            "severity": "critical",
            "lat": 14.5995,
            "lng": 120.9842,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-001","region":"NCR","affected":15000}',
        },
        {
            "external_id": "mock-inc-002",
            "title": "Magnitude 6.2 earthquake near Cebu City",
            "type": "earthquake",
            "severity": "high",
            "lat": 10.3157,
            "lng": 123.8854,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-002","depth_km":12,"magnitude":6.2}',
        },
        {
            "external_id": "mock-inc-003",
            "title": "Wildfire spreading across Palawan highlands",
            "type": "fire",
            "severity": "high",
            "lat": 9.8349,
            "lng": 118.7384,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-003","area_ha":340,"containment_pct":10}',
        },
        {
            "external_id": "mock-inc-004",
            "title": "Typhoon Amang approaching Eastern Samar",
            "type": "storm",
            "severity": "critical",
            "lat": 11.5000,
            "lng": 125.5000,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-004","wind_kph":185,"category":4}',
        },
        {
            "external_id": "mock-inc-005",
            "title": "Flash floods in Cagayan de Oro",
            "type": "flood",
            "severity": "medium",
            "lat": 8.4822,
            "lng": 124.6472,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-005","rainfall_mm":280,"displaced":800}',
        },
        {
            "external_id": "mock-inc-006",
            "title": "Volcanic ashfall from Mayon Volcano",
            "type": "other",
            "severity": "medium",
            "lat": 13.2575,
            "lng": 123.6858,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-006","alert_level":3,"ashfall_radius_km":15}',
        },
        {
            "external_id": "mock-inc-007",
            "title": "Landslide blocking national highway in Benguet",
            "type": "other",
            "severity": "high",
            "lat": 16.4023,
            "lng": 120.5960,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-007","road_closed_km":4,"trapped":23}',
        },
        {
            "external_id": "mock-inc-008",
            "title": "Coastal storm surge in Leyte Gulf",
            "type": "storm",
            "severity": "high",
            "lat": 10.8800,
            "lng": 125.0200,
            "source": "mock_data",
            "raw_data": '{"external_id":"mock-inc-008","surge_height_m":3.2,"evacuated":1200}',
        },
    ]


def get_mock_resources() -> List[dict]:
    """
    Return 12 realistic resources distributed across Southeast Asia.
    Each dict conforms to ResourceCreate field names.
    """
    return [
        {
            "name": "Manila Medical Response Team Alpha",
            "type": "medical",
            "lat": 14.6091,
            "lng": 121.0223,
            "capacity": 50,
        },
        {
            "name": "Cebu Rescue Squad 1",
            "type": "rescue",
            "lat": 10.3300,
            "lng": 123.9000,
            "capacity": 20,
        },
        {
            "name": "Davao Logistics Hub",
            "type": "logistics",
            "lat": 7.1907,
            "lng": 125.4553,
            "capacity": 200,
        },
        {
            "name": "Palawan Fire Brigade Unit 3",
            "type": "firefighting",
            "lat": 9.7392,
            "lng": 118.7353,
            "capacity": 15,
        },
        {
            "name": "Eastern Visayas Shelter Network",
            "type": "shelter",
            "lat": 11.2442,
            "lng": 125.0039,
            "capacity": 500,
        },
        {
            "name": "Mindanao Rescue Helicopter Unit",
            "type": "rescue",
            "lat": 8.0000,
            "lng": 124.0000,
            "capacity": 8,
        },
        {
            "name": "National Capital Medical Reserve",
            "type": "medical",
            "lat": 14.5500,
            "lng": 121.0500,
            "capacity": 100,
        },
        {
            "name": "Bicol Emergency Logistics Team",
            "type": "logistics",
            "lat": 13.4200,
            "lng": 123.4100,
            "capacity": 80,
        },
        {
            "name": "Iloilo Firefighting Unit 2",
            "type": "firefighting",
            "lat": 10.7202,
            "lng": 122.5621,
            "capacity": 12,
        },
        {
            "name": "Samar Community Shelter Alpha",
            "type": "shelter",
            "lat": 11.7000,
            "lng": 125.0000,
            "capacity": 300,
        },
        {
            "name": "Cordillera Search and Rescue",
            "type": "rescue",
            "lat": 16.4100,
            "lng": 120.5900,
            "capacity": 25,
        },
        {
            "name": "Central Luzon Medical Unit",
            "type": "medical",
            "lat": 15.4800,
            "lng": 120.9600,
            "capacity": 60,
        },
  ]

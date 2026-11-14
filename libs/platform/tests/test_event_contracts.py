"""Contract consistency test for backlog task I1-02 (event contracts).

`contracts/events/registry.json` is the machine-readable form of SAD 7.2 (event list) and
SAD 7.3 (RabbitMQ topology) that `libs/platform` will use to declare the topology (I1-03).
These tests keep the registry, the event schemas and the examples in agreement, using the
standard library only (schema validation of the examples is done by
`.github/scripts/validate-contracts.sh`).
"""

import json
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
EVENTS_DIR = REPO_ROOT / "contracts" / "events"
SHARED_SCHEMAS = {"envelope.schema.json", "common.schema.json"}

# SAD 7.2: event, publisher, consumers.
SAD_7_2 = {
    "RestaurantRegistered": ("restaurant", {"catalog", "order"}),
    "RestaurantSuspended": ("restaurant", {"catalog", "order"}),
    "CustomerRegistered": ("identity", {"analytics"}),
    "MenuItemUpdated": ("catalog", {"conversation"}),
    "MenuItemAvailabilityChanged": ("catalog", {"conversation"}),
    "PromotionActivated": ("catalog", {"conversation"}),
    "PromotionExpired": ("catalog", {"conversation"}),
    "OrderCreated": ("order", {"notification", "analytics"}),
    "OrderUpdated": ("order", {"notification", "analytics"}),
    "OrderStatusChanged": ("order", {"notification", "analytics"}),
    "OrderCancelled": ("order", {"notification", "analytics"}),
    "SuggestionShown": ("conversation", {"analytics"}),
    "SuggestionAccepted": ("conversation", {"analytics"}),
    "SuggestionDeclined": ("conversation", {"analytics"}),
}

# SAD 7.3: queue per consumer and its bindings.
SAD_7_3_QUEUES = {
    "notification.q": {"order.*"},
    "analytics.q": {"order.*", "suggestion.*", "customer.*"},
    "conversation.q": {"catalog.*"},
    "catalog.q": {"restaurant.*"},
    "order.q": {"restaurant.*"},
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


REGISTRY = _load(EVENTS_DIR / "registry.json")
ENTRIES = {entry["event_type"]: entry for entry in REGISTRY["events"]}


def _svc(name: str) -> str:
    return f"{name}-service"


def test_registry_lists_exactly_the_events_of_sad_7_2() -> None:
    assert set(ENTRIES) == set(SAD_7_2)
    assert len(REGISTRY["events"]) == len(SAD_7_2), "duplicate registry entry"


@pytest.mark.parametrize("event_type", sorted(SAD_7_2))
def test_registry_producer_and_consumers_match_sad_7_2(event_type: str) -> None:
    producer, consumers = SAD_7_2[event_type]
    entry = ENTRIES[event_type]
    assert entry["producer"] == _svc(producer)
    assert set(entry["consumers"]) == {_svc(c) for c in consumers}


def test_every_event_schema_file_is_registered() -> None:
    files = {p.name for p in EVENTS_DIR.glob("*.schema.json")} - SHARED_SCHEMAS
    assert files == {entry["schema"] for entry in ENTRIES.values()}


@pytest.mark.parametrize("event_type", sorted(SAD_7_2))
def test_schema_constants_match_the_registry(event_type: str) -> None:
    entry = ENTRIES[event_type]
    schema = _load(EVENTS_DIR / entry["schema"])
    assert schema["allOf"] == [{"$ref": "envelope.schema.json"}], (
        "must compose the SAD 7.1 envelope"
    )
    props = schema["properties"]
    assert props["event_type"] == {"const": event_type}
    assert props["event_version"] == {"const": entry["event_version"]}
    assert props["producer"] == {"const": entry["producer"]}


@pytest.mark.parametrize("event_type", sorted(SAD_7_2))
def test_example_matches_the_registry(event_type: str) -> None:
    entry = ENTRIES[event_type]
    example = _load(EVENTS_DIR / "examples" / f"{event_type}.json")
    assert example["event_type"] == event_type
    assert example["event_version"] == entry["event_version"]
    assert example["producer"] == entry["producer"]


@pytest.mark.parametrize("event_type", sorted(SAD_7_2))
def test_routing_key_reaches_exactly_the_listed_consumers(event_type: str) -> None:
    """SAD 7.3: each consumer's queue receives the event, and no other queue does."""
    entry = ENTRIES[event_type]
    key = entry["routing_key"]
    aggregate, _, event = key.partition(".")
    assert aggregate and event and "." not in event, f"{key} is not <aggregate>.<event>"
    receiving = {
        queue["consumer"]
        for queue in REGISTRY["queues"]
        if any(fnmatchcase(key, binding) for binding in queue["bindings"])
    }
    assert receiving == set(entry["consumers"])


def test_queues_and_retry_topology_match_sad_7_3() -> None:
    assert REGISTRY["exchange"] == {"name": "domain.events", "type": "topic", "durable": True}
    assert {q["name"]: set(q["bindings"]) for q in REGISTRY["queues"]} == SAD_7_3_QUEUES
    for queue in REGISTRY["queues"]:
        assert queue["name"] == f"{queue['consumer'].removesuffix('-service')}.q"
    retry = REGISTRY["retry"]
    assert [(q["suffix"], q["ttl_ms"]) for q in retry["queues"]] == [
        (".retry.10s", 10_000),
        (".retry.1m", 60_000),
        (".retry.5m", 300_000),
    ]
    assert retry["max_attempts"] == 3
    assert retry["dlq_suffix"] == ".dlq"


def test_sad_7_1_sample_is_the_order_created_example() -> None:
    example = _load(EVENTS_DIR / "examples" / "OrderCreated.json")
    assert example["event_id"] == "8f14e45f-ceea-467a-9a4b-2c1d8e0b7a21"
    assert example["tenant_id"] == "rest_42"
    assert example["data"]["total"] == sum(
        line["qty"] * line["unit_price"] for line in example["data"]["items"]
    )

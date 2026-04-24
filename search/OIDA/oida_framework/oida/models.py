from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class Precondition:
    name: str
    weight: float
    verified: bool

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Precondition":
        try:
            name = str(data["name"])
            weight = float(data["weight"])
            verified = bool(data["verified"])
        except KeyError as exc:
            raise ValueError(f"Missing precondition field: {exc}") from exc
        if weight <= 0:
            raise ValueError(f"Precondition weight must be > 0 for '{name}'.")
        return Precondition(name=name, weight=weight, verified=verified)


@dataclass(slots=True)
class Event:
    id: str
    pattern_id: str
    task: str
    capability: float
    reversibility: float
    observability: float
    blast_radius: float
    completion: float
    tests_pass: float
    operator_accept: float
    benefit: float
    preconditions: List[Precondition]
    constitutive_parents: List[str] = field(default_factory=list)
    supportive_parents: List[str] = field(default_factory=list)
    invalidates_pattern: bool = False

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Event":
        required = [
            "id",
            "pattern_id",
            "task",
            "capability",
            "reversibility",
            "observability",
            "blast_radius",
            "completion",
            "tests_pass",
            "operator_accept",
            "benefit",
            "preconditions",
        ]
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Missing event fields for event {data.get('id', '<unknown>')}: {missing}")

        event = Event(
            id=str(data["id"]),
            pattern_id=str(data["pattern_id"]),
            task=str(data["task"]),
            capability=float(data["capability"]),
            reversibility=float(data["reversibility"]),
            observability=float(data["observability"]),
            blast_radius=float(data["blast_radius"]),
            completion=float(data["completion"]),
            tests_pass=float(data["tests_pass"]),
            operator_accept=float(data["operator_accept"]),
            benefit=float(data["benefit"]),
            preconditions=[Precondition.from_dict(item) for item in data["preconditions"]],
            constitutive_parents=[str(x) for x in data.get("constitutive_parents", [])],
            supportive_parents=[str(x) for x in data.get("supportive_parents", [])],
            invalidates_pattern=bool(data.get("invalidates_pattern", False)),
        )
        for field_name in [
            "capability",
            "reversibility",
            "observability",
            "blast_radius",
            "completion",
            "tests_pass",
            "operator_accept",
            "benefit",
        ]:
            value = getattr(event, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"Field '{field_name}' for event '{event.id}' must be in [0, 1]. Got {value}."
                )
        return event


@dataclass(slots=True)
class Scenario:
    name: str
    description: str
    config: Dict[str, float]
    events: List[Event]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Scenario":
        if "events" not in data or not isinstance(data["events"], list) or not data["events"]:
            raise ValueError("Scenario must contain a non-empty 'events' list.")
        return Scenario(
            name=str(data.get("name", "unnamed_scenario")),
            description=str(data.get("description", "")),
            config={str(k): float(v) for k, v in data.get("config", {}).items()},
            events=[Event.from_dict(item) for item in data["events"]],
        )

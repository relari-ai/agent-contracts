import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer

from .contract import Contract


class Scenario(BaseModel):
    uuid: str
    name: Optional[str] = None
    data: Any
    contracts: List[Contract] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, data: Any, uuid: Optional[str] = None, **kwargs):
        super().__init__(data=data, uuid=uuid or self.generate_uuid(data), **kwargs)

    @field_serializer("contracts")
    def serialize_contracts(self, contracts: List[Contract]):
        return [contract.model_dump(exclude_defaults=True) for contract in contracts]

    @staticmethod
    def generate_uuid(data: Any, name: Optional[str] = None):
        try:
            string_repr = str(data).encode()
        except Exception:
            try:
                string_repr = str(data.__dict__).encode()
            except Exception:
                string_repr = str(name).encode() if name else os.urandom(64)
        return hashlib.blake2b(string_repr, digest_size=4).hexdigest()

    def get_contract(self, uuid: str):
        for contract in self.contracts:
            if contract.uuid == uuid:
                return contract
        raise KeyError(f"UUID {uuid} not found in scenario")


class Dataset(BaseModel):
    uuid: str
    scenarios: List[Scenario]

    def __init__(self, scenarios: List[Scenario], uuid: Optional[str] = None, **kwargs):
        if not uuid:
            scenarios_repr = json.dumps([s.model_dump() for s in scenarios])
            uuid = hashlib.blake2b(scenarios_repr.encode(), digest_size=4).hexdigest()
        super().__init__(scenarios=scenarios, uuid=uuid, **kwargs)

    def __post_init__(self):
        uuids = {scenario.uuid for scenario in self.scenarios}
        if len(uuids) != len(self.scenarios):
            raise ValueError("Duplicate UUIDs found in dataset")

    @field_serializer("scenarios")
    def serialize_scenarios(self, scenarios: List[Scenario]):
        return [scenario.model_dump(exclude_defaults=True) for scenario in scenarios]

    def __getitem__(self, uuid: str):
        for scenario in self.scenarios:
            if scenario.uuid == uuid:
                return scenario
        raise KeyError(f"UUID {uuid} not found in dataset")

    def __setitem__(self, uuid: str, scenario: Scenario):
        for i, d in enumerate(self.scenarios):
            if d.uuid == uuid:
                self.scenarios[i] = scenario
                return
        self.scenarios.append(scenario)

    def __iter__(self):
        return iter(self.scenarios)

    def __len__(self):
        return len(self.scenarios)

    def save(self, path: str):
        path = Path(path)
        if path.suffix == ".json":
            with open("dataset.json", "w") as f:
                json.dump(self.model_dump(exclude_defaults=True), f)
        else:
            raise ValueError(f"Unsupported file extension: {path.suffix}")

    @classmethod
    def load(cls, path: str):
        path = Path(path)
        if path.suffix == ".json":
            data = json.load(open(path, "r"))
            scenarios = [Scenario(**scenario) for scenario in data["scenarios"]]
            return cls(scenarios=scenarios, uuid=data["uuid"])
        else:
            raise ValueError(f"Unsupported file extension: {path.suffix}")

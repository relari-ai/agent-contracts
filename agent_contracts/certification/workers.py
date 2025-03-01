import asyncio
import base64
import json
from typing import List

import dramatiq
import redis
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware.asyncio import AsyncIO
from loguru import logger

from agent_contracts.certification.config import RuntimeVerificationConfig
from agent_contracts.core.datatypes.specifications import Contract, Specifications
from agent_contracts.core.datatypes.specifications.requirement import Level
from agent_contracts.core.datatypes.trace import Trace
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.contract_checker import (
    Condition,
    ContractChecker,
)

broker = RedisBroker(url=RuntimeVerificationConfig.redis.url)
broker.add_middleware(AsyncIO())
dramatiq.set_broker(broker)

redis_client = redis.Redis(
    host=RuntimeVerificationConfig.redis.host,
    port=RuntimeVerificationConfig.redis.port,
    decode_responses=True,
)


specification = Specifications.load(RuntimeVerificationConfig.specifications)


def task(dec):
    def decorator(func):
        if RuntimeVerificationConfig.debug:
            # Return the function unchanged, not decorated.
            return func
        return dec(func)

    return decorator


def _preprocess_spans(raw_spans: list[dict]):
    spans = []
    for span in raw_spans:
        _span = {
            "spanID": span["spanId"],
            "parentSpanID": span["parentSpanId"] if "parentSpanId" in span else None,
            "name": span["name"],
            "kind": span["kind"],
            "attributes": span["attributes"],
            "startTime": span["startTimeUnixNano"],
            "endTime": span["endTimeUnixNano"],
            "resource": {"attributes": span["resource"]["attributes"]},
        }
        spans.append(_span)
    return spans


def kafka2trace(trace_id: str, spans: list[dict]):
    return Trace(trace_id=trace_id, trace=_preprocess_spans(spans))


async def _active_contracts(exec_path: ExecutionPath):
    active_contracts = []
    for scenario in specification.scenarios:
        for contract in scenario.contracts:
            group = [
                req.check(ContractChecker.prepare_requirement_input(req, exec_path))
                for req in contract.preconditions
                if req.level == Level.MUST
            ]
            preconditions = await asyncio.gather(*group)
            active = all(p.satisfied for p in preconditions)
            if active:
                active_contracts.append(contract)
    return active_contracts


async def _verify_contract(
    checker: ContractChecker, exec_path: ExecutionPath, contract: Contract
):
    result = await checker.check(
        exec_path,
        contract,
        filter=Condition.PATHCONDITIONS | Condition.POSTCONDITIONS,
    )
    return contract.uuid, result


async def _check_contracts(active_contracts: List[Contract], exec_path: ExecutionPath):
    checker = ContractChecker()
    group = [
        _verify_contract(checker, exec_path, contract) for contract in active_contracts
    ]
    results = await asyncio.gather(*group)
    return {uuid: res for uuid, res in results}


@task(dramatiq.actor)
async def certify_span(trace_id: str, spans: List[dict]):
    logger.info(f"[{trace_id}] Starting new certification")
    hex_trace_id = base64.b64decode(trace_id).hex()
    trace = kafka2trace(hex_trace_id, spans)
    exec_path = ExecutionPath.from_trace(trace)
    active_contracts = await _active_contracts(exec_path)
    if not active_contracts:
        logger.info(f"[{trace_id}] No active contracts")
        redis_client.setex(
            f"{RuntimeVerificationConfig.key}:{exec_path.trace_id}",
            RuntimeVerificationConfig.ttl,
            json.dumps({}),
        )
        return
    logger.info(f"[{trace_id}] Active contracts: {len(active_contracts)}")
    # Delete previous results, we are going to update it soon
    redis_client.delete(f"{RuntimeVerificationConfig.key}:{trace_id}")
    results = await _check_contracts(active_contracts, exec_path)
    payload = json.dumps(
        {
            contract_id: {
                "requirements": {
                    rid: r.model_dump(exclude_unset=True, exclude_none=True)
                    for rid, r in res.info.items()
                },
            }
            for contract_id, res in results.items()
        }
    )
    logger.info(f"[{trace_id}] Certificate {exec_path.trace_id}: {payload}")
    redis_client.setex(
        f"{RuntimeVerificationConfig.key}:{exec_path.trace_id}",
        RuntimeVerificationConfig.ttl,
        payload,
    )
    logger.info(f"[{trace_id}] Certification completed")

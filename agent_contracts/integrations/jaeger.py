import aiohttp
from datetime import datetime, timezone
from agent_contracts.core.utils.trace_attributes import get_attribute_value
from agent_contracts.core.datatypes.trace import Trace
from .base import TraceInfo


def _preprocess_spans(trace: dict):
    spans = []
    for span in trace["data"][0]["spans"]:
        _span = {
            "spanID": span["spanID"],
            "parentSpanID": (
                span["references"][0]["spanID"] if span["references"] else None
            ),
            "name": span["operationName"],
            "kind": None,
            "attributes": span["tags"],
            "startTime": span["startTime"],
            "endTime": (span["startTime"] + span["duration"]),
            "resource": {"attributes": trace["data"][0]["processes"]["p1"]["tags"]},
        }
        spans.append(_span)
    return spans


def jaeger2trace(trace_id: str, trace_data: dict):
    trace = Trace(
        trace_id=trace_id,
        trace=_preprocess_spans(trace_data),
    )
    return trace


class JaegerClient:
    def __init__(self, base_url="http://localhost:16686", timeout=10):
        """
        Initialize the Jaeger Integration.

        :param base_url: Base URL of the Jaeger Query API (e.g., "http://localhost:16686")
        :param timeout: HTTP request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_trace_info(self, traces: list[dict]) -> list[TraceInfo]:
        trace_infos = []
        for trace_data in traces:
            run_id = get_attribute_value(
                trace_data["resource"]["attributes"], key="eval.run.id"
            )
            dataset_id = get_attribute_value(
                trace_data["scopeSpans"][1]["spans"][0]["attributes"],
                key="eval.dataset.id",
            )
            scenario_id = get_attribute_value(
                trace_data["scopeSpans"][1]["spans"][0]["attributes"],
                key="eval.uuid",
            )
            project_name = get_attribute_value(
                trace_data["resource"]["attributes"], key="openinference.project.name"
            )
            trace_id = trace_data["scopeSpans"][1]["spans"][0]["traceId"]
            start_time = trace_data["scopeSpans"][1]["spans"][0]["startTimeUnixNano"]
            end_time = trace_data["scopeSpans"][1]["spans"][0]["endTimeUnixNano"]
            trace_infos.append(
                TraceInfo(
                    trace_id=trace_id,
                    project_name=project_name,
                    run_id=run_id,
                    dataset_id=dataset_id,
                    scenario_id=scenario_id,
                    start_time=datetime.fromtimestamp(int(start_time) / 1e9),
                    end_time=datetime.fromtimestamp(int(end_time) / 1e9),
                )
            )
        return trace_infos

    async def search(self, service, start, end):
        # Convert datetime objects to RFC 3339 strings if necessary.
        if isinstance(start, datetime):
            start = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(end, datetime):
            end = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        url = f"{self.base_url}/api/v3/traces"
        params = {
            "query.service_name": service,
            "query.start_time_min": start,
            "query.start_time_max": end,
        }
        data = []
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = {"Accept": "application/json"}
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
                    if data.get("error"):
                        raise RuntimeError(f"API Error: {data.get('error')}")
                    data = data.get("result", data)
        except Exception as e:
            raise RuntimeError("Failed to search traces from Jaeger") from e
        return self._get_trace_info(data["resourceSpans"])

    async def trace(self, trace_id):
        """
        Get a specific trace from Jaeger by its trace ID asynchronously.

        :param trace_id: (str) The unique identifier for the trace.
        :return: Trace data (dict)
        :raises RuntimeError: When the HTTP request fails.
        """
        url = f"{self.base_url}/api/traces/{trace_id}"

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            raise RuntimeError("Failed to get trace from Jaeger") from e


class Jaeger:
    def __init__(
        self,
        base_url: str = "http://localhost:16686",
        service: str = "relari-otel",
        timeout: int = 10,
    ):
        self.client = JaegerClient(base_url, timeout)
        self.service = service

    async def search(self, start: datetime, end: datetime):
        traces = await self.client.search(self.service, start, end)
        return traces

    async def trace(self, trace_id: str):
        trace_data = await self.client.trace(trace_id)
        return jaeger2trace(trace_id, trace_data)

    async def run_ids(self, start: datetime, end: datetime):
        traces = await self.search(start, end)
        run_ids = {
            get_attribute_value(trace["resource"], key="eval.run.id")
            for trace in traces["resourceSpans"]
        } - {None}
        return list(run_ids)

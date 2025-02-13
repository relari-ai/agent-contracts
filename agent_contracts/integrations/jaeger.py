import aiohttp
from datetime import datetime, timezone
from agent_contracts.core.utils.trace_attributes import get_attribute_value
from agent_contracts.core.datatypes.trace import Trace
from .base import TraceInfo, RunIdInfo


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
            if e.status == 404:
                return {"resourceSpans": []}
            else:
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

    async def search(
        self,
        start: datetime,
        end: datetime,
        run_id: str = None,
        dataset_id: str = None,
        project_name: str = None,
    ):
        traces = await self.client.search(self.service, start, end)
        if run_id:
            traces = [trace for trace in traces if trace.run_id == run_id]
        if dataset_id:
            traces = [trace for trace in traces if trace.dataset_id == dataset_id]
        if project_name:
            traces = [trace for trace in traces if trace.project_name == project_name]
        return traces

    async def trace(self, trace_id: str):
        trace_data = await self.client.trace(trace_id)
        return jaeger2trace(trace_id, trace_data)

    async def run_ids(self, start: datetime, end: datetime):
        traces = await self.search(start, end)
        aggregated = {}
        for trace in traces:
            run_id = trace.run_id
            if run_id not in aggregated:
                aggregated[run_id] = {
                    "run_id": run_id,
                    "project_name": trace.project_name,
                    "dataset_id": trace.dataset_id,
                    "start_time": trace.start_time,
                    "end_time": trace.end_time,
                }
            else:
                aggregated[run_id]["start_time"] = min(
                    aggregated[run_id]["start_time"], trace.start_time
                )
                aggregated[run_id]["end_time"] = max(
                    aggregated[run_id]["end_time"], trace.end_time
                )
        return [RunIdInfo(**data) for data in aggregated.values()]

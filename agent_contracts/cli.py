import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import click
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from agent_contracts.core.datatypes.dataset.contract import Contract
from agent_contracts.core.datatypes.dataset.dataset import Dataset
from agent_contracts.core.datatypes.trace import Trace
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.contract_checker import ContractChecker
from agent_contracts.integrations.jaeger import Jaeger


class CLIAdapter:
    def __init__(self):
        self.client = Jaeger()
        self.console = Console()

    def preprocess_time_args(
        self,
        start: Optional[datetime],
        end: Optional[datetime],
        timespan: Optional[str],
    ) -> Tuple[datetime, datetime]:
        if start and end:
            return self.preprocess_start_end(start, end)
        elif timespan:
            return self.preprocess_timespan(timespan)
        else:
            raise ValueError("Either --start and --end or --timespan must be provided.")

    def preprocess_timespan(self, timespan: str) -> Tuple[datetime, datetime]:
        if timespan:
            end = datetime.now(timezone.utc)
            if timespan.endswith("h"):
                start = datetime.now(timezone.utc) - timedelta(hours=int(timespan[:-1]))
            elif timespan.endswith("d"):
                start = datetime.now(timezone.utc) - timedelta(days=int(timespan[:-1]))
            else:
                raise ValueError("Invalid timespan. Must be in the format nh or nd.")
            return start, end

    def preprocess_start_end(
        self, start: str | datetime, end: str | datetime
    ) -> Tuple[datetime, datetime]:
        if isinstance(start, str):
            start = datetime.strptime(start, "%Y-%m-%d")
        if isinstance(end, str):
            end = datetime.strptime(end, "%Y-%m-%d")
        start = start.replace(hour=0, minute=0, second=0)
        end = end.replace(hour=23, minute=59, second=59)
        return start, end

    async def _verify_single_trace(
        self, trace: Trace, dataset: Dataset, checker: ContractChecker
    ):
        async def _verify_contract(exec_path: ExecutionPath, contract: Contract):
            result = await checker.check(exec_path, contract)
            return contract.uuid, result

        exec_path = ExecutionPath.from_trace(trace)
        try:
            scenario = dataset[trace.info.uuid]
        except KeyError:
            raise RuntimeError(f"Scenario {trace.info.uuid} not found in dataset")
        group = [
            _verify_contract(exec_path, contract) for contract in scenario.contracts
        ]
        results = await asyncio.gather(*group)
        results = {uuid: res for uuid, res in results}
        return results

    async def verify_trace(
        self, trace_id: str, dataset_path: Path, output: Optional[Path] = None
    ):
        """Verify a trace with the given TRACE_ID and DATASET_PATH."""
        click.echo(f"Verifying trace {trace_id} with dataset at {dataset_path}")
        dataset = Dataset.load(dataset_path)
        trace = await self.client.trace(trace_id)
        if trace.info.dataset_id != dataset.uuid:
            raise RuntimeError("Trace does not match the dataset")
        scenario = dataset[trace.info.uuid]
        checker = ContractChecker()
        results = await self._verify_single_trace(trace, dataset, checker)
        if output:
            with open(output, "w") as f:
                json.dump(
                    {
                        "trace_id": trace_id,
                        "dataset_id": dataset.uuid if dataset else None,
                        "contracts": {
                            contract.uuid: {
                                "status": results[contract.uuid][0].name,
                                "requirements": {
                                    rid: r.model_dump(
                                        exclude_unset=True, exclude_none=True
                                    )
                                    for rid, r in results[contract.uuid][1].items()
                                },
                            }
                            for contract in scenario.contracts
                        },
                    },
                    f,
                )
        for contract in scenario.contracts:
            cstatus, cresults = results[contract.uuid]
            contract_table = Table(title=f"{contract.name} ({cstatus.name})")
            contract_table.add_column(
                "Type", justify="left", style="cyan", no_wrap=True
            )
            contract_table.add_column(
                "Qualifier", justify="left", style="cyan", no_wrap=True
            )
            contract_table.add_column(
                "Requirement", justify="left", style="cyan", no_wrap=False
            )
            contract_table.add_column("Satisfied", justify="left", no_wrap=True)
            for qreq in contract:
                contract_table.add_row(
                    qreq.section.value.upper(),
                    qreq.qualifier.value.upper(),
                    qreq.requirement.name,
                    (
                        "[green]Yes[/green]"
                        if cresults[qreq.requirement.uuid].satisfied
                        else "[red]No[/red]"
                    ),
                )
            self.console.print(contract_table)

    async def verify_run(
        self,
        run_id: str,
        dataset_path: Path,
        start: datetime,
        end: datetime,
        output: Optional[Path] = None,
    ):
        """Verify a run with the given DATASET_PATH."""

        async def _verify_trace(trace_id: str, dataset: Dataset, cc: ContractChecker):
            trace = await self.client.trace(trace_id)
            return trace.trace_id, await self._verify_single_trace(trace, dataset, cc)

        dataset = Dataset.load(dataset_path)
        traces = await self.client.search(start, end, run_id=run_id)
        traces_by_id = {trace.trace_id: trace for trace in traces}
        if not traces_by_id:
            click.echo(f"No traces found for run {run_id}, done.")
            return
        if not all(trace.dataset_id == dataset.uuid for trace in traces):
            click.echo(
                "Warning: Traces does not match the dataset, trying to verify anyway..."
            )
        missing_scenarios = []
        for trace in traces:
            if trace.scenario_id not in dataset:
                missing_scenarios.append(trace.scenario_id)
        if missing_scenarios:
            click.Abort(
                f"Scenarios {missing_scenarios} not found in dataset, aborting..."
            )
        cc = ContractChecker()
        group = [_verify_trace(trace.trace_id, dataset, cc) for trace in traces]
        results = await asyncio.gather(*group)
        results = {uuid: res for uuid, res in results}
        if output:
            with open(output, "w") as f:
                rex = [
                    {
                        "trace_id": trace_id,
                        "dataset_id": dataset.uuid if dataset else None,
                        "contracts": {
                            contract_id: {
                                "status": contract_inner_results[0].name,
                                "requirements": {
                                    rid: r.model_dump(
                                        exclude_unset=True, exclude_none=True
                                    )
                                    for rid, r in contract_inner_results[1].items()
                                },
                            }
                            for contract_id, contract_inner_results in contract_results.items()
                        },
                    }
                    for trace_id, contract_results in results.items()
                ]
                json.dump(rex, f)
        for trace_id, contract_results in results.items():
            self.console.print(Rule(f"Trace {trace_id}"))
            scenario = dataset[traces_by_id[trace_id].scenario_id]
            for contract_id, contract_inner_results in contract_results.items():
                cstatus, cresults = contract_inner_results
                contract = scenario.get_contract(contract_id)
                contract_table = Table(title=f"{contract.name} ({cstatus.name})")
                contract_table.add_column(
                    "Type", justify="left", style="cyan", no_wrap=True
                )
                contract_table.add_column(
                    "Qualifier", justify="left", style="cyan", no_wrap=True
                )
                contract_table.add_column(
                    "Requirement", justify="left", style="cyan", no_wrap=False
                )
                contract_table.add_column("Satisfied", justify="left", no_wrap=True)
                for qreq in contract:
                    contract_table.add_row(
                        qreq.section.value.upper(),
                        qreq.qualifier.value.upper(),
                        qreq.requirement.name,
                        (
                            "[green]Yes[/green]"
                            if cresults[qreq.requirement.uuid].satisfied
                            else "[red]No[/red]"
                        ),
                    )
                self.console.print(contract_table)
        return results

    async def list_trace(self, start: datetime, end: datetime, timespan: str):
        """List traces between START and END dates or based on a timespan."""
        if timespan:
            # Handle timespan logic here
            click.echo(f"Listing traces for timespan: {timespan}")
            if timespan.endswith("h"):
                start = datetime.now(timezone.utc) - timedelta(hours=int(timespan[:-1]))
                end = datetime.now(timezone.utc)
            elif timespan.endswith("d"):
                start = datetime.now(timezone.utc) - timedelta(days=int(timespan[:-1]))
                end = datetime.now(timezone.utc)
        traces = await self.client.search(start, end)
        console = Console()
        table = Table()
        # Add columns to the table
        table.add_column("Trace ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Project Name", justify="left", style="cyan", no_wrap=False)
        table.add_column("Run ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Dataset ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Scenario ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Start Time", justify="left", style="cyan", no_wrap=False)
        table.add_column("End Time", justify="left", style="cyan", no_wrap=False)
        for trace in traces:
            table.add_row(
                trace.trace_id,
                trace.project_name,
                trace.run_id,
                trace.dataset_id,
                trace.scenario_id,
                trace.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                trace.end_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        # Print the table to the console
        console.print(table)

    async def list_run(self, start, end, timespan):
        """List runs between START and END dates."""
        if timespan:
            if timespan.endswith("h"):
                start = datetime.now(timezone.utc) - timedelta(hours=int(timespan[:-1]))
                end = datetime.now(timezone.utc)
            elif timespan.endswith("d"):
                start = datetime.now(timezone.utc) - timedelta(days=int(timespan[:-1]))
                end = datetime.now(timezone.utc)
        click.echo(f"Listing runs from {start} to {end}")
        runs = await self.client.run_ids(start, end)
        console = Console()
        table = Table()
        table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
        table.add_column("Project Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Dataset ID", justify="left", style="cyan", no_wrap=True)
        table.add_column("Start Time", justify="left", style="cyan", no_wrap=True)
        table.add_column("End Time", justify="left", style="cyan", no_wrap=True)
        for run in runs:
            table.add_row(
                run.run_id,
                run.project_name,
                run.dataset_id,
                run.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                run.end_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        console.print(table)

    async def get_trace(self, trace_id, output: Path):
        """Get details of the trace with the given TRACE_ID."""
        trace = await self.client.trace(trace_id)
        exec_path = ExecutionPath.from_trace(trace)
        with open(output, "w") as f:
            json.dump(exec_path.model_dump(), f)

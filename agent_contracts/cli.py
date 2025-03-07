import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import click
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from agent_contracts.core.datatypes.specifications import Contract, Specifications
from agent_contracts.core.datatypes.trace import Trace
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.contract_checker import ContractChecker
from agent_contracts.integrations.jaeger import Jaeger


async def _verify_contract(
    checker: ContractChecker, exec_path: ExecutionPath, contract: Contract
):
    result = await checker.check(exec_path, contract)
    return contract.uuid, result



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
        self, trace: Trace, specifications: Specifications, checker: ContractChecker
    ):
        async def _verify_contract(
            checker: ContractChecker, exec_path: ExecutionPath, contract: Contract
        ):
            result = await checker.check(exec_path, contract)
            return contract.uuid, result

        exec_path = ExecutionPath.from_trace(trace)
        try:
            scenario = specifications[trace.info.scenario_id]
        except KeyError:
            raise RuntimeError(
                f"Scenario {trace.info.scenario_id} not found in specifications"
            )
        group = [
            _verify_contract(exec_path, contract) for contract in scenario.contracts
        ]
        results = await asyncio.gather(*group)
        results = {uuid: res for uuid, res in results}
        return results

    async def verify_trace(
        self, trace_id: str, specifications_path: Path, output: Optional[Path] = None
    ):
        """Verify a trace with the given TRACE_ID and SPECIFICATIONS_PATH."""
        click.echo(
            f"Verifying trace {trace_id} with specifications at {specifications_path}"
        )
        try:
            specification = Specifications.load(specifications_path)
        except Exception:
            click.echo(f"Error loading specifications from {specifications_path}")
            raise click.Abort()
        trace = await self.client.trace(trace_id)
        if trace.info.specifications_id != specification.uuid:
            raise RuntimeError("Trace does not match the specifications")
        try:
            scenario = specification[trace.info.scenario_id]
        except KeyError:
            raise RuntimeError(
                f"Scenario {trace.info.scenario_id} not found in specifications"
            )
        exec_path = ExecutionPath.from_trace(trace)
        checker = ContractChecker()
        group = [
            _verify_contract(checker, exec_path, contract)
            for contract in scenario.contracts
        ]
        results = await asyncio.gather(*group)
        results = {uuid: res for uuid, res in results}
        if output:
            with open(output, "w") as f:
                json.dump(
                    {
                        "trace_id": trace.trace_id,
                        "specification_id": (
                            specification.uuid if specification else None
                        ),
                        "contracts": {
                            contract_id: {
                                "status": res.satisfied.name,
                                "requirements": {
                                    rid: r.model_dump(
                                        exclude_unset=True, exclude_none=True
                                    )
                                    for rid, r in res.info.items()
                                },
                            }
                            for contract_id, res in results.items()
                        },
                    },
                    f,
                    indent=2,
                )
        for contract in scenario.contracts:
            cx = results[contract.uuid]
            tab = Table(title=f"{contract.name} ({cx.satisfied.name})")
            tab.add_column("ID", justify="left", style="cyan", no_wrap=True)
            tab.add_column("Type", justify="left", style="cyan", no_wrap=True)
            tab.add_column("Qualifier", justify="left", style="cyan", no_wrap=True)
            tab.add_column("Requirement", justify="left", style="cyan", no_wrap=False)
            tab.add_column("Satisfied", justify="left", no_wrap=True)
            for req in contract:
                tab.add_row(
                    req.uuid,
                    req.type.replace("condition", "").upper(),
                    req.level.name.upper(),
                    req.name,
                    (
                        "[green]Yes[/green]"
                        if cx.info[req.uuid].satisfied
                        else "[red]No[/red]"
                    ),
                )
            self.console.print(tab)

    async def verify_run(
        self,
        run_id: str,
        specifications_path: Path,
        start: datetime,
        end: datetime,
        output: Optional[Path] = None,
    ):
        """Verify a run with the given SPECIFICATIONS_PATH."""
        async def _verify_trace(trace_id: str, specs: Specifications):
            trace = await self.client.trace(trace_id)
            exec_path = ExecutionPath.from_trace(trace)
            cc = ContractChecker()
            scenario = specs[trace.info.scenario_id]
            group = [
                _verify_contract(cc, exec_path, contract)
                for contract in scenario.contracts
            ]
            results = await asyncio.gather(*group)
            results = {uuid: res for uuid, res in results}
            return trace.trace_id, results
        
        try:
            specification = Specifications.load(specifications_path)
        except Exception:
            click.echo(f"Error loading specifications from {specifications_path}")
            raise click.Abort()
        traces = await self.client.search(start, end, run_id=run_id)
        traces_by_id = {trace.trace_id: trace for trace in traces}
        if not traces_by_id:
            click.echo(f"No traces found for run {run_id}, done.")
            return
        if not all(trace.specifications_id == specification.uuid for trace in traces):
            click.echo(
                "Warning: Traces does not match the specifications, trying to verify anyway..."
            )
        missing_scenarios = []
        for trace in traces:
            if trace.scenario_id not in specification:
                missing_scenarios.append(trace.scenario_id)
        if missing_scenarios:
            click.echo(
                f"Scenarios {missing_scenarios} not found in specifications, aborting..."
            )
            raise click.Abort()

        
        group = [_verify_trace(trace.trace_id, specification) for trace in traces]
        results = await asyncio.gather(*group)
        results = {uuid: res for uuid, res in results}
        if output:
            with open(output, "w") as f:
                rex = [
                    {
                        "trace_id": trace_id,
                        "specifications_id": specification.uuid, 
                        "scenario_id": traces_by_id[trace_id].scenario_id,
                        "contracts": {
                            contract_id: {
                                "status": cx.satisfied.name,
                                "info": {
                                    rid: r.model_dump(
                                        exclude_unset=True, exclude_none=True
                                    )
                                    for rid, r in cx.info.items()
                                },
                            }
                            for contract_id, cx in contract_results.items()
                        },
                    }
                    for trace_id, contract_results in results.items()
                ]
                json.dump(rex, f)
        for trace_id, contract_results in results.items():
            self.console.print(Rule(f"Trace {trace_id}"))
            scenario = specification[traces_by_id[trace_id].scenario_id]
            for contract_id, cx in contract_results.items():
                contract = scenario.get_contract(contract_id)
                contract_table = Table(title=f"{contract.name} ({cx.satisfied.name})")
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
                        qreq.type.replace("condition","").upper(),
                        qreq.level.name.upper(),
                        qreq.name,
                        (
                            "[green]Yes[/green]"
                            if cx.info[qreq.uuid].satisfied
                            else "[red]No[/red]"
                        ),
                    )
                self.console.print(contract_table)
        return results

    async def list_trace(self, start: datetime, end: datetime):
        """List traces between START and END dates."""
        traces = await self.client.search(start, end)
        if traces == {"resourceSpans": []}:
            click.echo("No traces found")
            return
        console = Console()
        table = Table()
        table.add_column("Trace ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Project Name", justify="left", style="cyan", no_wrap=False)
        table.add_column("Run ID", justify="left", style="cyan", no_wrap=False)
        table.add_column(
            "Specifications ID", justify="left", style="cyan", no_wrap=False
        )
        table.add_column("Scenario ID", justify="left", style="cyan", no_wrap=False)
        table.add_column("Start Time", justify="left", style="cyan", no_wrap=False)
        table.add_column("End Time", justify="left", style="cyan", no_wrap=False)
        for trace in traces:
            table.add_row(
                trace.trace_id,
                trace.project_name,
                trace.run_id,
                trace.specifications_id,
                trace.scenario_id,
                trace.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                trace.end_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        # Print the table to the console
        console.print(table)

    async def list_run(self, start, end):
        """List runs between START and END dates."""
        runs = await self.client.run_ids(start, end)
        if not runs:
            click.echo("No runs found")
            return
        console = Console()
        table = Table()
        table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
        table.add_column("Project Name", justify="left", style="cyan", no_wrap=True)
        table.add_column(
            "Specifications ID", justify="left", style="cyan", no_wrap=True
        )
        table.add_column("Start Time", justify="left", style="cyan", no_wrap=True)
        table.add_column("End Time", justify="left", style="cyan", no_wrap=True)
        for run in runs:
            table.add_row(
                run.run_id,
                run.project_name,
                run.specifications_id,
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

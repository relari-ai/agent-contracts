import asyncio
import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agent_contracts.core.datatypes.dataset.dataset import Dataset
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.contract_checker import ContractChecker
from agent_contracts.integrations.jaeger import Jaeger


def coroutine(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


jaeger = Jaeger()


@click.group()
def cli():
    """Agent Contracts CLI"""
    pass


@cli.command()
@click.argument("trace_id", type=str)
@click.argument("dataset_path", type=Path)
@click.option("--output", type=Path, required=False)
@coroutine
async def verify_trace(trace_id, dataset_path, output):
    """Verify a trace with the given TRACE_ID and DATASET_PATH."""
    click.echo(f"Verifying trace {trace_id} with dataset at {dataset_path}")
    dataset = Dataset.load(dataset_path)
    trace = await jaeger.trace(trace_id)
    if trace.info.dataset_id != dataset.uuid:
        raise RuntimeError("Trace does not match the dataset")
    exec_path = ExecutionPath.from_trace(trace)
    scenario = dataset[trace.info.uuid]
    results = {}
    checker = ContractChecker()
    for contract in scenario.contracts:
        results[contract.uuid] = await checker.check(exec_path, contract)
    if output:
        with open(output, "w") as f:
            json.dump(results, f)
    console = Console()
    for contract in scenario.contracts:
        cstatus, cresults = results[contract.uuid]
        contract_table = Table(title=f"{contract.name} ({cstatus.name})")
        contract_table.add_column("Type", justify="left", style="cyan", no_wrap=True)
        contract_table.add_column("Qualifier", justify="left", style="cyan", no_wrap=True)
        contract_table.add_column("Requirement", justify="left", style="cyan", no_wrap=False)
        contract_table.add_column("Satisfied", justify="left", no_wrap=True)
        for qreq in contract:
            contract_table.add_row(
                qreq.section.value.upper(),
                qreq.qualifier.value.upper(),
                qreq.requirement.name,
                "[green]Yes[/green]" if cresults[qreq.requirement.uuid] else "[red]No[/red]",
            )
        console.print(contract_table)


@cli.command()
@click.argument("run_id", type=str)
@click.argument("dataset_path", type=Path)
@coroutine
async def verify_run(run_id, dataset_path):
    """Verify a run with the given DATASET_PATH."""
    click.echo(f"Verifying run {run_id} with dataset at {dataset_path}")
    dataset = Dataset.load(dataset_path)
    # traces = await jaeger.run_ids(run_id)
    # for trace in traces:
    #     await verify_trace(trace.trace_id, dataset_path)


@cli.command()
@click.option("--start", type=str, help="Start time in format YYYY-MM-DDor xH/xD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD or xH/xD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@coroutine
async def list_trace(start, end, timespan):
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
    traces = await jaeger.search(start, end)
    console = Console()
    table = Table()
    # Add columns to the table
    table.add_column("Trace ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Project Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Dataset ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Scenario ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Start Time", justify="left", style="cyan", no_wrap=True)
    table.add_column("End Time", justify="left", style="cyan", no_wrap=True)
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


@cli.command()
@click.argument("start", type=click.DateTime(formats=["%Y-%m-%d %H:%M:%S"]))
@click.argument("end", type=click.DateTime(formats=["%Y-%m-%d %H:%M:%S"]))
def list_run(start, end):
    """List runs between START and END dates."""
    click.echo(f"Listing runs from {start} to {end}")


@cli.command()
@click.argument("trace_id", type=str)
@click.argument("output", type=Path, required=False)
@coroutine
async def get_trace(trace_id, output):
    """Get details of the trace with the given TRACE_ID."""
    trace = await jaeger.trace(trace_id)
    exec_path = ExecutionPath.from_trace(trace)
    if not output:
        output = Path(f"{trace_id}.json")
    with open(output, "w") as f:
        json.dump(exec_path.model_dump(), f)


if __name__ == "__main__":
    cli()

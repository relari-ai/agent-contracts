import asyncio
from functools import wraps
from pathlib import Path

import click

from agent_contracts.cli import CLIAdapter

adapter = CLIAdapter()


def coroutine(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


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
    """Verify a trace with the given TRACE_ID and DATASET_PATH.

    TRACE_ID: The unique identifier for the trace to verify.
    DATASET_PATH: The path to the dataset file used for verification.
    --output: Optional path to save the verification results in JSON format.
    """
    if output:
        output = Path(output)
        if output.exists():
            raise click.BadParameter(f"Output path {output} already exists")
        output.parent.mkdir(parents=True, exist_ok=True)
    if not dataset_path.exists():
        raise click.BadParameter(f"Dataset path {dataset_path} does not exist")
    await adapter.verify_trace(trace_id, dataset_path, output)


@cli.command()
@click.argument("run_id", type=str)
@click.argument("dataset_path", type=Path)
@click.option("--start", type=str, help="Start time in format YYYY-MM-DD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@click.option("--output", type=Path, required=False)
@coroutine
async def verify_run(run_id, dataset_path, start, end, timespan, output):
    """Verify a run with the given RUN_ID and DATASET_PATH.

    RUN_ID: The unique identifier for the run to verify.
    DATASET_PATH: The path to the dataset file used for verification.
    --start: Optional start time in format YYYY-MM-DD.
    --end: Optional end time in format YYYY-MM-DD.
    --timespan: Optional timespan in format nh (n hours) or nd (n days).
    """
    try:
        start, end = adapter.preprocess_time_args(start, end, timespan)
    except ValueError as e:
        raise click.BadParameter(e.message)
    if not dataset_path.exists():
        raise click.BadParameter(f"Dataset path {dataset_path} does not exist")
    if output:
        if output.exists():
            raise click.BadParameter(f"Output path {output} already exists")
        output.parent.mkdir(parents=True, exist_ok=True)
    click.echo(
        f"Verifying run {run_id} with dataset at {dataset_path} from {start} to {end}"
    )
    await adapter.verify_run(run_id, dataset_path, start, end, output)


@cli.command()
@click.option("--start", type=str, help="Start time in format YYYY-MM-DD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@coroutine
async def list_trace(start, end, timespan):
    """List traces within the specified time range.

    This command retrieves and lists traces that fall within the given start and end times.

    --start: Optional start time in format YYYY-MM-DD.
    --end: Optional end time in format YYYY-MM-DD.
    --timespan: Optional timespan in format nh (n hours) or nd (n days).
    """
    try:
        start, end = adapter.preprocess_time_args(start, end, timespan)
    except ValueError as e:
        raise click.BadParameter(e.message)
    await adapter.list_trace(start, end, timespan)


@cli.command()
@click.option("--start", type=str, help="Start time in format YYYY-MM-DD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@coroutine
async def list_run(start, end, timespan):
    """List runs within the specified time range.

    This command retrieves and lists runs that fall within the given start and end times.

    --start: Optional start time in format YYYY-MM-DD.
    --end: Optional end time in format YYYY-MM-DD.
    --timespan: Optional timespan in format nh (n hours) or nd (n days).
    """
    try:
        start, end = adapter.preprocess_time_args(start, end, timespan)
    except ValueError as e:
        raise click.BadParameter(e.message)
    await adapter.list_run(start, end, timespan)


@cli.command()
@click.argument("trace_id", type=str)
@click.argument("output", type=Path, required=False)
@coroutine
async def get_trace(trace_id, output):
    """Get the trace with the given TRACE_ID.

    TRACE_ID: The unique identifier for the trace to get details of.
    --output: Optional path to save the trace details in JSON format.
    """
    if output:
        output = Path(output)
        if output.exists():
            raise click.BadParameter(f"Output path {output} already exists")
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        output = Path(f"{trace_id}.json")
    click.echo(f"Getting trace {trace_id} and saving to {output}")
    await adapter.get_trace(trace_id, output)


if __name__ == "__main__":
    cli()

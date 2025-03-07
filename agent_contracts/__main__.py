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
    """Main CLI entrypoint."""
    pass


#######################################################################################
# Group: verify
#######################################################################################
@cli.group()
def verify():
    """Start verification on traces or runs."""
    pass


@verify.command()
@click.argument("trace_id", type=str)
@click.argument("specs", type=Path)
@click.option(
    "--output-dir",
    type=Path,
    required=False,
    default=Path("output"),
    help="Output directory, results will be saved as verify_<TRACE_ID>.json in this directory",
    show_default=True,
)
@coroutine
async def trace(trace_id, specs, output_dir):
    """Start the verification process on a trace.

    \b
    TRACE_ID: The unique identifier for the trace to verify.
    SPECS: Path to the specifications file used for verification.
    """
    if not specs.exists():
        click.echo(f"Specifications file {specs} does not exist")
        raise click.Abort()
    fname = output_dir / f"verify_{trace_id}.json"
    if fname.exists():
        if not click.confirm(f"Output file {fname} already exists. Override?"):
            raise click.Abort()
    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Verifying trace {trace_id} with specifications from {specs}...")
    click.echo(f"Output will be saved to {fname}")
    try:
        await adapter.verify_trace(trace_id, specs, fname)
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()
    click.echo("Done")


@verify.command()
@click.argument("run_id", type=str)
@click.argument("specs", type=Path)
@click.option("--start", type=str, help="Start time in format YYYY-MM-DD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@click.option(
    "--output-dir",
    type=Path,
    required=False,
    default=Path("output"),
    help="Output directory, results will be saved as verify_<RUN_ID>.json in this directory",
    show_default=True,
)
@coroutine
async def run(run_id, specs, output_dir, start, end, timespan):
    """Start the verification of a run.

    \b
    RUN_ID: The unique identifier for the run to verify.
    SPECS: Path to the specifications file used for verification.
    """
    try:
        start, end = adapter.preprocess_time_args(start, end, timespan)
    except ValueError as e:
        click.echo(f"Invalid time range: {e.args[0]}")
        raise click.Abort()
    if not specs.exists():
        click.echo(f"Specifications file {specs} does not exist")
        raise click.Abort()
    fname = output_dir / f"verify_{run_id}.json"
    if fname.exists():
        if not click.confirm(f"Output file {fname} already exists. Override?"):
            raise click.Abort()
    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Verifying run {run_id} with specifications from {specs}...")
    click.echo(f"Output will be saved to {fname}")
    try:
        await adapter.verify_run(run_id, specs, start, end, fname)
    except Exception as e:
        click.echo(f"Error: {e}")
        raise click.Abort()


#######################################################################################
# Group: get
#######################################################################################
@cli.group()
def get():
    """Get traces from the server."""
    pass


@get.command()
@click.argument("trace_id", type=str)
@click.option(
    "--output-dir",
    type=Path,
    required=False,
    default=Path("output"),
    help="Output directory, trace will be saved as trace_<TRACE_ID>.json in this directory",
    show_default=True,
)
@coroutine
async def trace(trace_id, output_dir):  # noqa: F811
    """Get a trace as JSON.

    TRACE_ID: The unique identifier for the trace to get.
    """
    fname = output_dir / f"trace_{trace_id}.json"
    if fname.exists():
        if not click.confirm(f"Output file {fname} already exists. Override?"):
            raise click.Abort()
    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Downloading trace {trace_id} to {fname}...")
    await adapter.get_trace(trace_id, fname)
    click.echo("Done")


#######################################################################################
# Group: ls
#######################################################################################
@cli.group(name="ls")
def ls_group():
    """List traces and runs."""
    pass


@ls_group.command(name="trace")
@click.option("--start", type=str, help="Start time in format YYYY-MM-DD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@coroutine
async def ls_trace(start, end, timespan):
    """List traces within the specified time range."""
    try:
        start, end = adapter.preprocess_time_args(start, end, timespan)
    except ValueError as e:
        click.echo(f"Invalid time range: {e.args[0]}")
        raise click.Abort()
    click.echo(f"Listing traces from {start} to {end}...")
    await adapter.list_trace(start, end)


@ls_group.command(name="run")
@click.option("--start", type=str, help="Start time in format YYYY-MM-DD")
@click.option("--end", type=str, help="End time in format YYYY-MM-DD")
@click.option(
    "--timespan", type=str, help="Timespan in format nh (n hours) or nd (n days)"
)
@coroutine
async def ls_runs(start, end, timespan):
    """List runs within the specified time range."""
    try:
        start, end = adapter.preprocess_time_args(start, end, timespan)
    except ValueError as e:
        click.echo(f"Invalid time   : {e.args[0]}")
        raise click.Abort()
    click.echo(f"Listing runs from {start} to {end}...")
    await adapter.list_run(start, end)


if __name__ == "__main__":
    cli()

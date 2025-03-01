# Agent Contracts

## Overview

Agent Contracts is a tool for verifying the contracts of agentic systems.

## Offline Verification

### Prerequisites

- Run background services `make docker`
- TODO, complete CLI and show example

### Runtime Verification

#### Prerequisites

#### Client code

In the client code, initialize the OTel package with certification enabled.

```python
Relari.init(project_name="my-project-name", batch=False, certification_enabled=True)
```

Notice that batch must be set to `False` if certification is enabled.

To access the certificate you can use `cert = Relari.wait_for_cert()` in your code. This will block the execution until the certificate is ready, and timeout after 60 seconds (the timeout can be changed).

For example:

```python
async def main():
  with Relari.start_new_sample(scenario_id="my-scenario-id") as sample:
    run_your_code()
    cert = Relari.wait_for_cert()
    print(f"Cert: {cert}")
```

##### Services

The certification server relies on Kafka and Redis. First, run the services with `make docker-runtime-certification`.

##### Configuration

There is a configuration file for the runtime verification service in `configs/runtime-verification.yaml`.
If `debug` is set to `true`, the service will run in debug mode (slower, synchronous workers). Otherwise, it will run in asynchronous mode (faster, asynchronous workers).

If `debug` is set to `false` (asynchronous workers), you need to also start the workers.

```bash
make runtime-certification-workers
```

### Run

In the terminal run

```bash
export RUNTIME_VERIFICATION_CONFIG="configs/runtime-verification.yaml" && \
poetry run python3 agent_contracts/certification/runtime_verification.py 
```

Or use the "Certification" debugger profile in VSCode/Cursor.

Now you can run app should see a certificate after the execution.

from agent_contracts.integrations.jaeger import Jaeger
import asyncio
from datetime import datetime, timezone, timedelta
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.core.verification.contract_checker import ContractChecker
from agent_contracts.core.datatypes.dataset.dataset import Dataset
jaeger = Jaeger()

end = datetime.now(timezone.utc)
start = end - timedelta(hours=6)

# async def main():   
#     # r = await jaeger.run_ids(start, end)
#     dataset = Dataset.load("/Users/antonap/relari/relari-2.0/axon/local_store/datasets/dataset-3-unique.json")
#     trace = await jaeger.trace("3c3a62b13533cacf92c8a9b985f2def2")
#     assert trace.info.dataset_id == dataset.uuid, "Trace is not from the dataset"
#     exec_path = ExecutionPath.from_trace(trace)
#     scenario = dataset[trace.info.uuid]
#     results = {}
#     checker = ContractChecker()
#     for contract in scenario.contracts:
#         results[contract.uuid] = await checker.check(exec_path, contract)
#     print(results)

async def main(): 
    start = datetime.now(timezone.utc) - timedelta(hours=3)
    end = datetime.now(timezone.utc)
    traces = await jaeger.search(start, end)
    print(traces)
asyncio.run(main())

import argparse
import asyncio
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Tree, Pretty 
from textual.containers import VerticalScroll
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.integrations.jaeger import Jaeger
import json
from agent_contracts.integrations.jaeger import jaeger2trace

class TreeApp(App):
    CSS_PATH = "layout.tcss"

    def __init__(self, trace: str|Path, **kwargs):
        super().__init__(**kwargs)
        self._input_trace = trace
        self.jaeger = Jaeger()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield Tree("Execution Path", classes="exec_path")
        yield VerticalScroll(Pretty("Info", id="pretty_content"), classes="info")

    def build_tree(self) -> None:
        tree = self.query_one(Tree)
        root = tree.root
        for state in self.execution_path.states:
            state_node = root.add(state.name, data=state)
            for action in state.actions:
                state_node.add_leaf(action.name, data=action)
        root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """When a tree node is selected, update the Pretty widget with that node's info 
        and display the span ID at the top (if available)."""
        node = event.node
        data = node.data

        # Get the base info. If not available, show a default message.
        base_info = data.info if data and hasattr(data, "info") else "No additional info available."
        
        # Retrieve the span ID from the node's data if it exists.
        # Here we assume that a span ID is stored in the attribute "span_id".
        span_id = getattr(data, "span_id", None)
        
        # Compose the text with the span ID on top (if available), then additional info.
        if span_id:
            combined_info = f"Span ID: {span_id}\n\n{base_info}"
        else:
            combined_info = base_info

        pretty_widget = self.query_one("#pretty_content", expect_type=Pretty)
        pretty_widget.update(combined_info)

    async def on_mount(self) -> None:
        """Load JSON from the provided path and initialize the tree with nodes."""
        # self.execution_path = ExecutionPath.load(Path(self.file_path))
        if isinstance(self._input_trace, Path):
            with open(self._input_trace, "r") as f:
                trace_data = json.load(f)
            self.trace_id = trace_data["data"][0]["traceID"]
            self.trace = jaeger2trace(self.trace_id, trace_data)
        else:
            self.trace_id = self._input_trace
            self.trace = await self.jaeger.trace(self.trace_id)
        self.execution_path = ExecutionPath.from_trace(self.trace)
        self.build_tree()

def main():
    parser = argparse.ArgumentParser(description="TUI Execution Path Viewer")
    parser.add_argument("trace", help="Trace ID or JSON file")
    args = parser.parse_args()
    if args.trace.endswith(".json"):
        trace_path = Path(args.trace)
        if trace_path.exists():
            app = TreeApp(trace=trace_path)
        else:
            raise RuntimeError(f"Trace file {trace_path} does not exist")
    else:
        app = TreeApp(trace_id=args.trace)
    asyncio.run(app.run())

if __name__ == "__main__":
    main()

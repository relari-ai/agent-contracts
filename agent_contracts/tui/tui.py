import argparse
import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Tree, Pretty 
from textual.containers import VerticalScroll
from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath
from agent_contracts.integrations.jaeger import Jaeger

class TreeApp(App):
    CSS_PATH = "layout.tcss"

    def __init__(self, trace_id: str, **kwargs):
        super().__init__(**kwargs)
        self.trace_id = trace_id
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
        """When a tree node is selected, update the Pretty widget with that node's info."""
        node = event.node
        data = node.data
        info = data.info if data and hasattr(data, "info") else "No info available"
        pretty_widget = self.query_one("#pretty_content", expect_type=Pretty)
        pretty_widget.update(info)

    async def on_mount(self) -> None:
        """Load JSON from the provided path and initialize the tree with nodes."""
        # self.execution_path = ExecutionPath.load(Path(self.file_path))
        trace = await self.jaeger.trace(self.trace_id)
        self.execution_path = ExecutionPath.from_trace(trace)
        self.build_tree()

def main():
    parser = argparse.ArgumentParser(description="TUI Execution Path Viewer")
    parser.add_argument("trace_id", help="Trace ID")
    args = parser.parse_args()
    app = TreeApp(trace_id=args.trace_id)
    asyncio.run(app.run())

if __name__ == "__main__":
    main()

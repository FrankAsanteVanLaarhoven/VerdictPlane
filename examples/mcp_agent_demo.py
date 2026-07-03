"""Example: an MCP-style agent whose tool-calls are governed by VerdictPlane.

The "agent" here is a scripted plan (read a file, then write one) driving an
MCP-style dispatch table. The point is the wiring: the agent holds only the
governed dispatch, so a write physically cannot happen without approval.

Run:  PYTHONPATH=src python examples/mcp_agent_demo.py
Then approve the pending write from another terminal with the P3 CLI, or
watch it fail safe on timeout.
"""

import os
import sys

from verdictplane import Gate, Ledger, load_policy
from verdictplane.mcp import governed_dispatch

WORKSPACE = "artifacts/demo_workspace"

TOOL_EFFECTS = {"read_file": "read", "write_file": "write", "list_dir": "read"}


def make_tools():
    os.makedirs(WORKSPACE, exist_ok=True)
    with open(os.path.join(WORKSPACE, "notes.txt"), "w") as f:
        f.write("meeting at 10\n")

    def dispatch(tool, arguments):
        path = os.path.join(WORKSPACE, arguments["path"])
        if tool == "read_file":
            with open(path) as f:
                return f.read()
        if tool == "write_file":
            with open(path, "w") as f:
                f.write(arguments["content"])
            return "written"
        if tool == "list_dir":
            return os.listdir(WORKSPACE)
        raise ValueError(f"unknown tool {tool}")

    return dispatch


def main():
    policy = load_policy("policies/mcp_demo.yaml")
    ledger = Ledger("artifacts/demo_ledger.jsonl")
    gate = Gate("artifacts/demo_gate")
    call_tool = governed_dispatch(
        make_tools(), policy=policy, ledger=ledger, gate=gate,
        effect_of=TOOL_EFFECTS, agent="demo-agent", gate_timeout=60,
    )

    # the agent's plan: read, then write
    print("agent: read_file ->", call_tool("read_file", {"path": "notes.txt"}).strip())
    print("agent: write_file (blocks for approval; approve via verdictplane CLI)...")
    print("agent:", call_tool("write_file", {"path": "notes.txt", "content": "rescheduled\n"}))


if __name__ == "__main__":
    sys.exit(main())

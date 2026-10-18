import os
import sys
import json
import asyncio
import subprocess
from jsonschema import validate, ValidationError

class MCPStdioClient:
    """Asyncio JSON-RPC 2.0 Client over stdio sub-process transport."""
    def __init__(self, command, args):
        self.command = command
        self.args = args
        self.process = None
        self.req_id = 0

    async def start(self):
        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    async def send_request(self, method, params=None):
        self.req_id += 1
        payload = {"jsonrpc": "2.0", "id": self.req_id, "method": method}
        if params is not None:
            payload["params"] = params
        
        msg = json.dumps(payload) + "\n"
        self.process.stdin.write(msg.encode('utf-8'))
        await self.process.stdin.drain()

        response_line = await self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("MCP Server process terminated unexpectedly.")
        return json.loads(response_line.decode('utf-8'))

    async def close(self):
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass

async def run_harness():
    print("🚀 Initializing Production MCP Integration Test Harness...")
    client = MCPStdioClient(sys.executable, ["mcp_server.py"])
    await client.start()

    test_results = []
    all_passed = True

    try:
        # 1. Protocol Handshake
        init_res = await client.send_request("initialize")
        assert "result" in init_res and "capabilities" in init_res["result"], "Invalid initialize response"
        test_results.append({"step": "Protocol Handshake (stdio)", "status": "PASSED", "details": "JSON-RPC 2.0 handshake verified."})

        # 2. Tool Discovery & Schema Integrity Check
        tools_res = await client.send_request("tools/list")
        tools = tools_res.get("result", {}).get("tools", [])
        assert len(tools) > 0, "No tools discovered on MCP server"
        
        schema_failures = []
        for tool in tools:
            schema = tool.get("inputSchema", {})
            if not isinstance(schema, dict) or schema.get("type") != "object":
                schema_failures.append(f"Tool '{tool.get('name')}' missing valid inputSchema object")
        
        if schema_failures:
            test_results.append({"step": "Schema Structural Check", "status": "FAILED", "details": "; ".join(schema_failures)})
            all_passed = False
        else:
            test_results.append({"step": "Schema Structural Check", "status": "PASSED", "details": f"Discovered and validated {len(tools)} tool schemas."})

        # 3. Candidate Tool Invocation & Strict JSON Schema Draft-07 Validation
        candidate_tool_call = {
            "name": "calculate_token_cost",
            "arguments": {
                "prompt_tokens": 1500,
                "completion_tokens": 500,
                "model_name": "gpt-4o"
            }
        }

        target_tool = next((t for t in tools if t["name"] == candidate_tool_call["name"]), None)
        assert target_tool is not None, f"Target tool not found: {candidate_tool_call['name']}"

        try:
            validate(instance=candidate_tool_call["arguments"], schema=target_tool["inputSchema"])
            test_results.append({"step": "Strict JSON Schema Validation", "status": "PASSED", "details": "Arguments strictly conform to Draft-07 constraints."})
        except ValidationError as ve:
            test_results.append({"step": "Strict JSON Schema Validation", "status": "FAILED", "details": f"Schema Mismatch: {ve.message}"})
            all_passed = False

        # 4. Tool Execution
        exec_res = await client.send_request("tools/call", {
            "name": candidate_tool_call["name"],
            "arguments": candidate_tool_call["arguments"]
        })

        if "result" in exec_res and "content" in exec_res["result"]:
            tool_output = exec_res["result"]["content"][0]["text"]
            test_results.append({"step": "Tool Execution via stdio", "status": "PASSED", "details": f"Output: {tool_output}"})
        else:
            test_results.append({"step": "Tool Execution via stdio", "status": "FAILED", "details": f"Error: {exec_res.get('error')}"})
            all_passed = False

    except Exception as e:
        test_results.append({"step": "Harness Execution", "status": "FAILED", "details": str(e)})
        all_passed = False
    finally:
        await client.close()

    # Generate Markdown Summary Output
    summary_md = "## 🛡️ Agentic MCP Integration Test Report\n\n"
    summary_md += "| Test Step | Status | Execution Details |\n| :--- | :--- | :--- |\n"
    for item in test_results:
        icon = "✅" if item["status"] == "PASSED" else "❌"
        summary_md += f"| **{item['step']}** | {icon} `{item['status']}` | {item['details']} |\n"

    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary_path:
        with open(github_summary_path, "a") as f:
            f.write(summary_md)

    with open("README.md", "w") as f:
        f.write(summary_md + "\n\n*Automated production CI/CD test harness output.*")

    print(summary_md)

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_harness())

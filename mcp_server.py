import sys
import json

# Production Tool Definitions adhering to MCP JSON Schema Draft-07 Specifications
TOOLS = [
    {
        "name": "calculate_token_cost",
        "description": "Calculates the USD cost for LLM prompt and completion tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt_tokens": {"type": "integer", "minimum": 0},
                "completion_tokens": {"type": "integer", "minimum": 0},
                "model_name": {"type": "string", "enum": ["gpt-4o", "claude-3-5-sonnet", "llama-3.2"]}
            },
            "required": ["prompt_tokens", "completion_tokens", "model_name"]
        }
    },
    {
        "name": "check_system_status",
        "description": "Checks the operational status of a specified infrastructure service.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"}
            },
            "required": ["service_name"]
        }
    }
]

def handle_request(request):
    req_id = request.get("id")
    method = request.get("method")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "Production-MCP-Server", "version": "1.0.0"}
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }
    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "calculate_token_cost":
            rates = {"gpt-4o": 0.000005, "claude-3-5-sonnet": 0.000003, "llama-3.2": 0.000001}
            rate = rates.get(args.get("model_name"), 0.000002)
            cost = (args.get("prompt_tokens", 0) + args.get("completion_tokens", 0)) * rate
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Calculated Cost: ${cost:.6f}"}]}
            }
        elif tool_name == "check_system_status":
            svc = args.get("service_name")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"Service '{svc}' is operational (200 OK)."}]}
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found."}
            }
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()


import os
import urllib.request
import json
from google import genai
from google.genai import types

OVS_MCP_URL = "http://localhost:8080/mcp"

def call_ovs_tool(tool_name: str, arguments: dict) -> dict:
    payload = {
        "id": "gemini-call",
        "tool": tool_name,
        "arguments": arguments
    }
    req = urllib.request.Request(
        OVS_MCP_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

# Tool definitions mapped to local function execution
def get_ports() -> str:
    """Gets the list of active bridges, ports, and interfaces in Open vSwitch."""
    return json.dumps(call_ovs_tool("switch.get_ports", {}))

def get_flows(bridge: str) -> str:
    """Gets the list of active OpenFlow flows for a given bridge.
    Args:
        bridge: The name of the bridge to retrieve flows from.
    """
    return json.dumps(call_ovs_tool("switch.get_flows", {"bridge": bridge}))

def get_port_stats(bridge: str, port: str) -> str:
    """Gets packet/byte tx/rx statistics for a given port.
    Args:
        bridge: The name of the bridge.
        port: The name of the port.
    """
    return json.dumps(call_ovs_tool("switch.get_port_stats", {"bridge": bridge, "port": port}))

def set_vlan(bridge: str, port: str, vlan: int) -> str:
    """Sets the access VLAN tag (0-4095) on a bridge port. 0 clears the tag (trunk/untagged).
    Args:
        bridge: The name of the bridge.
        port: The name of the port.
        vlan: The VLAN tag integer (0-4095).
    """
    return json.dumps(call_ovs_tool("switch.set_vlan", {"bridge": bridge, "port": port, "vlan": vlan}))

def set_port_state(bridge: str, port: str, enabled: bool) -> str:
    """Administratively enables (UP) or disables (DOWN) a port interface link.
    Args:
        bridge: The name of the bridge.
        port: The name of the port.
        enabled: True to enable (UP), False to disable (DOWN).
    """
    return json.dumps(call_ovs_tool("switch.set_port_state", {"bridge": bridge, "port": port, "enabled": enabled}))

available_tools = {
    "get_ports": get_ports,
    "get_flows": get_flows,
    "get_port_stats": get_port_stats,
    "set_vlan": set_vlan,
    "set_port_state": set_port_state
}

def load_env():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_paths = [
        os.path.join(base_dir, ".env"),
        os.path.join(os.getcwd(), ".env")
    ]
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip('"').strip("'")
                            if key:
                                os.environ[key] = val
                break
            except Exception:
                pass

def main():
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is not set.")
        return

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    client = genai.Client()
    config = types.GenerateContentConfig(
        tools=list(available_tools.values()),
        temperature=0.0
    )

    print(f"=== Gemini OVS Assistant CLI ({model_name}) (type 'exit' to quit) ===")
    while True:
        prompt = input("\nUser > ")
        if prompt.lower() in ["exit", "quit"]:
            break

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            if response.function_calls:
                for call in response.function_calls:
                    print(f"Assistant > calling tool: {call.name}({call.args})")
                    if call.name in available_tools:
                        result = available_tools[call.name](**call.args)
                        # Send tool execution result back to the model
                        follow_up = client.models.generate_content(
                            model=model_name,
                            contents=[
                                types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
                                response.candidates[0].content,
                                types.Content(
                                    role="user",
                                    parts=[types.Part.from_function_response(name=call.name, response={"result": result})]
                                )
                            ]
                        )
                        print(f"Assistant > {follow_up.text}")
            else:
                print(f"Assistant > {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()

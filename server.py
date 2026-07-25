import asyncio
import json
import uuid
import sys
from typing import Any, Optional

import websockets
from websockets.asyncio.server import serve as ws_serve, ServerConnection
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

WS_HOST = "localhost"
WS_PORT = 9876

app = Server("roblox-mcp")

_pending: dict[str, asyncio.Future] = {}
_ws: Optional[ServerConnection] = None
_lock = asyncio.Lock()


async def ws_handler(websocket):
    global _ws
    async with _lock:
        _ws = websocket
    print(f"[MCP] Roblox connected", file=sys.stderr)
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                rid = msg.get("id")
                if rid and rid in _pending:
                    fut = _pending.pop(rid)
                    if msg.get("type") == "result":
                        fut.set_result(msg.get("value"))
                    elif msg.get("type") == "error":
                        fut.set_exception(RuntimeError(msg.get("error", "unknown")))
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"[MCP] Error processing message: {e}", file=sys.stderr)
    finally:
        async with _lock:
            _ws = None
        print(f"[MCP] Roblox disconnected", file=sys.stderr)


async def send_lua(code: str, timeout: float = 30.0) -> Any:
    async with _lock:
        if _ws is None:
            raise RuntimeError("Roblox is not connected. Run bridge.lua in Potassium first.")

    rid = uuid.uuid4().hex
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    _pending[rid] = fut

    payload = json.dumps({"id": rid, "type": "execute", "code": code})
    try:
        async with _lock:
            await _ws.send(payload)
    except Exception as e:
        _pending.pop(rid, None)
        raise RuntimeError(f"Error sending to Roblox: {e}")

    try:
        return await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError:
        _pending.pop(rid, None)
        raise RuntimeError("Timeout: Roblox did not respond in time")


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


TOOLS = [
    Tool(
        name="execute_lua",
        description="Runs arbitrary Lua code inside Roblox and returns the result.",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Lua code to execute. Use 'return' to return a value."
                }
            },
            "required": ["code"]
        }
    ),
    Tool(
        name="get_instances",
        description="Gets all game instances, optionally filtered by class.",
        inputSchema={
            "type": "object",
            "properties": {
                "class_name": {
                    "type": "string",
                    "description": "Filter by class name (e.g. 'Part', 'Script', 'RemoteEvent'). Empty = all."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 100)."
                }
            },
            "required": []
        }
    ),
    Tool(
        name="get_scripts",
        description="Lists all scripts in the game (Script, LocalScript, ModuleScript).",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 50)."
                }
            },
            "required": []
        }
    ),
    Tool(
        name="get_running_scripts",
        description="Lists all scripts currently running.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="get_loaded_modules",
        description="Lists all ModuleScripts loaded in memory.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="get_gc",
        description="Inspects objects in the garbage collector. Useful for finding specific objects.",
        inputSchema={
            "type": "object",
            "properties": {
                "class_filter": {
                    "type": "string",
                    "description": "Filter by class name (e.g. 'RemoteEvent', 'NumberValue')."
                },
                "name_filter": {
                    "type": "string",
                    "description": "Filter by object name."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 100)."
                }
            },
            "required": []
        }
    ),
    Tool(
        name="fire_signal",
        description="Fires a RemoteEvent, RemoteFunction or BindableEvent with arguments.",
        inputSchema={
            "type": "object",
            "properties": {
                "signal_path": {
                    "type": "string",
                    "description": "Path to the event (e.g. 'game.ReplicatedStorage.Remotes.MyEvent')."
                },
                "args_json": {
                    "type": "string",
                    "description": "Arguments in JSON format (e.g. '[1, \"hello\", true]')."
                }
            },
            "required": ["signal_path"]
        }
    ),
    Tool(
        name="hook_function",
        description="Hooks a function to intercept calls. Returns info about the original function.",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Lua code to get the reference to the function to hook. E.g. 'game.Players.LocalPlayer.Kick'."
                },
                "log_calls": {
                    "type": "boolean",
                    "description": "If true, logs every function call."
                }
            },
            "required": ["target"]
        }
    ),
    Tool(
        name="get_environment",
        description="Gets the global environment of a script (getsenv/getrenv).",
        inputSchema={
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Path to the script. If empty, returns Roblox global environment (getrenv)."
                },
                "max_keys": {
                    "type": "integer",
                    "description": "Maximum keys to return (default: 100)."
                }
            },
            "required": []
        }
    ),
    Tool(
        name="simulate_input",
        description="Simulates keyboard or mouse input in Roblox.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["keytap", "keypress", "keyrelease", "mouse1click", "mouse2click", "mousemove_abs", "mousemove_rel", "mousescroll"],
                    "description": "Input type."
                },
                "value": {
                    "type": "string",
                    "description": "For keys: keycode (e.g. 'W', 'Space', 'Return'). For mouse: coordinates (e.g. '100 200') or scroll amount."
                }
            },
            "required": ["type"]
        }
    ),
    Tool(
        name="read_file",
        description="Reads a file from the executor workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (relative to executor workspace)."
                }
            },
            "required": ["path"]
        }
    ),
    Tool(
        name="write_file",
        description="Writes a file to the executor workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path."
                },
                "content": {
                    "type": "string",
                    "description": "Content to write."
                }
            },
            "required": ["path", "content"]
        }
    ),
    Tool(
        name="list_files",
        description="Lists files in a directory of the executor workspace.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (default: root)."
                }
            },
            "required": []
        }
    ),
    Tool(
        name="http_request",
        description="Makes an HTTP request from inside Roblox (Roblox's IP, not yours).",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Request URL."
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, etc.). Default: GET."
                },
                "body": {
                    "type": "string",
                    "description": "Request body (for POST/PUT)."
                },
                "headers_json": {
                    "type": "string",
                    "description": "Headers in JSON format (e.g. '{\"Authorization\":\"Bearer xyz\"}')."
                }
            },
            "required": ["url"]
        }
    ),
    Tool(
        name="decompile_script",
        description="Decompiles a script into readable Lua code.",
        inputSchema={
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Path to the script (e.g. 'game.ReplicatedStorage.ModuleScript')."
                }
            },
            "required": ["script_path"]
        }
    ),
    Tool(
        name="save_instance",
        description="Saves a game instance as .rbxl or .rbxm file.",
        inputSchema={
            "type": "object",
            "properties": {
                "instance_path": {
                    "type": "string",
                    "description": "Path to the instance (e.g. 'workspace' or 'game.ReplicatedStorage.Map')."
                },
                "filename": {
                    "type": "string",
                    "description": "Output filename (e.g. 'map.rbxl')."
                }
            },
            "required": ["instance_path", "filename"]
        }
    ),
    Tool(
        name="set_clipboard",
        description="Copies text to the user's clipboard.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to copy."
                }
            },
            "required": ["text"]
        }
    ),
    Tool(
        name="get_player_info",
        description="Gets LocalPlayer information (name, userId, position, etc.).",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="teleport_to",
        description="Teleports the player to coordinates or to another player.",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Coordinates 'x y z' or player name."
                }
            },
            "required": ["target"]
        }
    ),
    Tool(
        name="drawing_create",
        description="Creates a visual object on screen (Text, Square, Line, Circle, Quad, Triangle, Image). Useful for making menus and ESP.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["Text", "Square", "Line", "Circle", "Quad", "Triangle", "Image"],
                    "description": "Type of drawing to create."
                },
                "properties_json": {
                    "type": "string",
                    "description": "Properties in JSON: Text, Size, Position, Color, Transparency, Visible, ZIndex, Font, Outline, etc. E.g. '{\"Text\":\"Hello\",\"Size\":20,\"Color\":\"255,0,0\"}'"
                }
            },
            "required": ["type"]
        }
    ),
    Tool(
        name="drawing_set",
        description="Changes a property of an existing drawing object.",
        inputSchema={
            "type": "object",
            "properties": {
                "object_var": {
                    "type": "string",
                    "description": "Name of the global variable where you saved the drawing (e.g. 'myText')."
                },
                "property": {
                    "type": "string",
                    "description": "Property name (e.g. 'Text', 'Visible', 'Color', 'Position')."
                },
                "value_json": {
                    "type": "string",
                    "description": "Value in JSON (e.g. '\"New text\"', 'true', '[100,200]')."
                }
            },
            "required": ["object_var", "property", "value_json"]
        }
    ),
    Tool(
        name="drawing_fonts",
        description="Lists available fonts for Text objects.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="drawing_clear",
        description="Removes all drawing objects from the screen.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="load_iy",
        description="Loads Infinite Yield in Roblox (script hub with 200+ commands: fly, noclip, esp, goto, btools, god, invisible, freeze, etc.). MUST be run first before using execute_iy.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="execute_iy",
        description="Executes an Infinite Yield command. Requires having run load_iy first. Use the command without the ';' prefix. E.g. 'fly 50', 'goto player', 'esp', 'noclip', 'btools', 'invisible', 'respawn', 'god', 'freeze all', 'loopgoto player', 'serverhop', 'dance', 'spin', 'speed 100', 'jumppower 100', 'fullbright'.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "IY command without prefix. E.g. 'fly 100', 'goto all', 'esp', 'respawn', 'freeze all', 'btools', 'serverhop', 'dance', 'invisible', 'god', 'spin', 'speed 100'"
                }
            },
            "required": ["command"]
        }
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _execute_tool(name, arguments)
        text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
        return [TextContent(type="text", text=text)]
    except RuntimeError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def _execute_tool(name: str, args: dict) -> Any:
    if name == "execute_lua":
        return await send_lua(args["code"])

    elif name == "get_instances":
        class_name = args.get("class_name", "") or ""
        limit = args.get("limit", 100)
        class_filter = f'if v.ClassName == "{_escape(class_name)}"' if class_name else ""
        code = f"""
local res = {{}}
local count = 0
for _, v in getinstances() do
    if v.Parent then
        {"".join([" " + class_filter + " then"]) if class_filter else ""}
            count = count + 1
            if count <= {limit} then
                table.insert(res, {{Name = v.Name, Class = v.ClassName, Path = v:GetFullName()}})
            end
        {"end" if class_filter else ""}
    end
    if count >= {limit} then break end
end
return {{total = count, items = res}}
"""
        return await send_lua(code)

    elif name == "get_scripts":
        limit = args.get("limit", 50)
        code = f"""
local scripts = getscripts()
local res = {{}}
for i, s in ipairs(scripts) do
    if i <= {limit} then
        table.insert(res, {{
            Name = s.Name,
            Class = s.ClassName,
            Path = s:GetFullName(),
            Hash = getscripthash(s)
        }})
    end
end
return {{total = #scripts, items = res}}
"""
        return await send_lua(code)

    elif name == "get_running_scripts":
        code = """
local scripts = getrunningscripts()
local res = {}
for i, s in ipairs(scripts) do
    table.insert(res, {
        Name = s.Name,
        Class = s.ClassName,
        Path = s:GetFullName()
    })
end
return {total = #scripts, items = res}
"""
        return await send_lua(code)

    elif name == "get_loaded_modules":
        code = """
local mods = getloadedmodules()
local res = {}
for i, m in ipairs(mods) do
    table.insert(res, {
        Name = m.Name,
        Path = m:GetFullName(),
        Hash = getscripthash(m)
    })
end
return {total = #mods, items = res}
"""
        return await send_lua(code)

    elif name == "get_gc":
        class_filter = args.get("class_filter", "") or ""
        name_filter = args.get("name_filter", "") or ""
        limit = args.get("limit", 100)
        conditions = []
        if class_filter:
            conditions.append(f'v.ClassName == "{_escape(class_filter)}"')
        if name_filter:
            conditions.append(f'v.Name == "{_escape(name_filter)}"')
        cond = " and ".join(conditions) if conditions else "true"
        code = f"""
local res = {{}}
local count = 0
for _, v in getgc() do
    if type(v) == "userdata" and v.Parent ~= nil and {cond} then
        count = count + 1
        if count <= {limit} then
            table.insert(res, {{Name = v.Name, Class = v.ClassName, Path = v:GetFullName()}})
        end
    end
end
return {{total = count, items = res}}
"""
        return await send_lua(code)

    elif name == "fire_signal":
        signal_path = args["signal_path"]
        args_json = args.get("args_json", "[]")
        code = f"""
local signal = {signal_path}
local args = game:GetService("HttpService"):JSONDecode('{_escape(args_json)}')
firesignal(signal, unpack(args))
return {{fired = true, signal = "{_escape(signal_path)}"}}
"""
        return await send_lua(code)

    elif name == "hook_function":
        target = args["target"]
        log = "true" if args.get("log_calls") else "false"
        code = f"""
local func = {target}
if typeof(func) ~= "function" then
    return {{error = "Target is not a function. Type: " .. typeof(func)}}
end
local old = hookfunction(func, function(...)
    if {log} then
        rconsoleinfo("[HOOK] {_escape(target)} called with args: " .. tostring({{...}}))
    end
    return old(...)
end)
return {{
    hooked = true,
    target = "{_escape(target)}",
    is_c_closure = iscclosure(old),
    is_l_closure = islclosure(old),
    already_hooked = isfunctionhooked(func)
}}
"""
        return await send_lua(code)

    elif name == "get_environment":
        script_path = args.get("script_path", "") or ""
        max_keys = args.get("max_keys", 100)
        if script_path:
            code = f"""
local env = getsenv({script_path})
if not env then return {{error = "Could not get environment of: {_escape(script_path)}"}} end
local keys = {{}}
local count = 0
for k, v in env do
    count = count + 1
    if count <= {max_keys} then
        table.insert(keys, tostring(k))
    end
end
return {{script = "{_escape(script_path)}", total_keys = count, keys = keys}}
"""
        else:
            code = f"""
local env = getrenv()
local keys = {{}}
local count = 0
for k, v in env do
    count = count + 1
    if count <= {max_keys} then
        table.insert(keys, tostring(k))
    end
end
return {{environment = "renv (Roblox global)", total_keys = count, keys = keys}}
"""
        return await send_lua(code)

    elif name == "simulate_input":
        input_type = args["type"]
        value = args.get("value", "")
        type_map = {
            "keytap": f'keytap("{_escape(value)}")',
            "keypress": f'keypress("{_escape(value)}")',
            "keyrelease": f'keyrelease("{_escape(value)}")',
            "mouse1click": "mouse1click()",
            "mouse2click": "mouse2click()",
            "mousemove_abs": f'mousemoveabs({value or "0 0"})',
            "mousemove_rel": f'mousemoverel({value or "0 0"})',
            "mousescroll": f'mousescroll({value or "0"})',
        }
        fn_call = type_map.get(input_type, f'keytap("{_escape(value)}")')
        code = f"{fn_call}\nreturn {{simulated = true, type = \"{_escape(input_type)}\"}}"
        return await send_lua(code)

    elif name == "read_file":
        path = args["path"]
        code = f'return readfile("{_escape(path)}")'
        return await send_lua(code)

    elif name == "write_file":
        path = args["path"]
        content = args["content"]
        content_escaped = content.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        code = f'writefile("{_escape(path)}", "{content_escaped}")\nreturn {{written = true, path = "{_escape(path)}"}}'
        return await send_lua(code)

    elif name == "list_files":
        path = args.get("path", "") or ""
        code = f'return listfiles("{_escape(path)}")' if path else "return listfiles('')"
        return await send_lua(code)

    elif name == "http_request":
        url = args["url"]
        method = args.get("method", "GET")
        body = args.get("body", "") or ""
        headers_json = args.get("headers_json", "{}")
        code = f"""
local headers = game:GetService("HttpService"):JSONDecode('{_escape(headers_json)}')
local opts = {{
    Url = "{_escape(url)}",
    Method = "{_escape(method)}",
    Body = "{_escape(body)}",
    Headers = headers
}}
local res = request(opts)
return {{
    success = res.Success,
    status_code = res.StatusCode,
    status_message = res.StatusMessage,
    body = res.Body:sub(1, 5000)
}}
"""
        return await send_lua(code)

    elif name == "decompile_script":
        script_path = args["script_path"]
        code = f"""
local s = {script_path}
local ok, result = pcall(decompile, s)
if ok then
    return {{script = "{_escape(script_path)}", source = result}}
else
    return {{error = tostring(result)}}
end
"""
        return await send_lua(code)

    elif name == "save_instance":
        instance_path = args["instance_path"]
        filename = args["filename"]
        code = f'saveinstance({instance_path}, "{_escape(filename)}")\nreturn {{saved = true, file = "{_escape(filename)}"}}'
        return await send_lua(code)

    elif name == "set_clipboard":
        text = args["text"]
        text_escaped = text.replace("\\", "\\\\").replace("\"", "\\\"")
        code = f'setclipboard("{text_escaped}")\nreturn {{copied = true}}'
        return await send_lua(code)

    elif name == "get_player_info":
        code = """
local lp = game:GetService("Players").LocalPlayer
local char = lp.Character
local root = char and char:FindFirstChild("HumanoidRootPart")
local humanoid = char and char:FindFirstChildOfClass("Humanoid")
return {
    Name = lp.Name,
    DisplayName = lp.DisplayName,
    UserId = lp.UserId,
    AccountAge = lp.AccountAge,
    Team = lp.Team and lp.Team.Name or nil,
    Position = root and {x = root.Position.X, y = root.Position.Y, z = root.Position.Z} or nil,
    Health = humanoid and humanoid.Health or nil,
    MaxHealth = humanoid and humanoid.MaxHealth or nil,
    WalkSpeed = humanoid and humanoid.WalkSpeed or nil
}
"""
        return await send_lua(code)

    elif name == "teleport_to":
        target = args["target"]
        parts = target.split()
        if len(parts) == 3 and all(p.replace(".", "").replace("-", "").isdigit() for p in parts):
            code = f"""
local lp = game:GetService("Players").LocalPlayer
local char = lp.Character
if char and char:FindFirstChild("HumanoidRootPart") then
    char.HumanoidRootPart.CFrame = CFrame.new({target})
    return {{teleported = true, position = "{target}"}}
else
    return {{error = "Character not found"}}
end
"""
        else:
            code = f"""
local lp = game:GetService("Players").LocalPlayer
local target_player = game:GetService("Players"):FindFirstChild("{_escape(target)}")
if not target_player then
    return {{error = "Player not found: {_escape(target)}"}}
end
local target_char = target_player.Character
if not target_char or not target_char:FindFirstChild("HumanoidRootPart") then
    return {{error = "Player character is not loaded"}}
end
local char = lp.Character
if char and char:FindFirstChild("HumanoidRootPart") then
    char.HumanoidRootPart.CFrame = target_char.HumanoidRootPart.CFrame + Vector3.new(0, 2, 0)
    return {{teleported = true, to_player = "{_escape(target)}"}}
else
    return {{error = "Your character is not loaded"}}
end
"""
        return await send_lua(code)

    elif name == "drawing_create":
        dtype = args["type"]
        props_json = args.get("properties_json", "{}")
        code = f"""
local props = game:GetService("HttpService"):JSONDecode('{_escape(props_json)}')
local d = Drawing.new("{_escape(dtype)}")
for k, v in pairs(props) do
    pcall(function()
        if k == "Color" and type(v) == "string" then
            local r, g, b = v:match("(%d+),(%d+),(%d+)")
            d[k] = Color3.fromRGB(tonumber(r) or 255, tonumber(g) or 255, tonumber(b) or 255)
        elseif k == "Position" and type(v) == "table" then
            d[k] = Vector2.new(v[1] or 0, v[2] or 0)
        else
            d[k] = v
        end
    end)
end
d.Visible = true
return {{created = true, type = "{_escape(dtype)}", text = d.Text, visible = d.Visible}}
"""
        return await send_lua(code)

    elif name == "drawing_set":
        obj_var = args["object_var"]
        prop = args["property"]
        val_json = args["value_json"]
        code = f"""
local val = game:GetService("HttpService"):JSONDecode('{_escape(val_json)}')
local d = {obj_var}
if not d then return {{error = "Object '{obj_var}' not found"}} end
if "{_escape(prop)}" == "Color" and type(val) == "string" then
    local r, g, b = val:match("(%d+),(%d+),(%d+)")
    d.Color = Color3.fromRGB(tonumber(r) or 255, tonumber(g) or 255, tonumber(b) or 255)
else
    d["{_escape(prop)}"] = val
end
return {{updated = true, object = "{obj_var}", property = "{prop}"}}
"""
        return await send_lua(code)

    elif name == "drawing_fonts":
        code = """
local fonts = {}
for _, f in pairs(Drawing.Fonts) do
    table.insert(fonts, tostring(f))
end
return fonts
"""
        return await send_lua(code)

    elif name == "drawing_clear":
        code = """
for _, v in getgc() do
    if typeof(v) == "table" and isrenderobj and pcall(isrenderobj, v) then
        pcall(function() v:Remove() end)
    end
end
return {cleared = true}
"""
        return await send_lua(code)

    elif name == "load_iy":
        code = """
if IY_LOADED then
    return {loaded = true, message = "Infinite Yield was already loaded"}
end
loadstring(game:HttpGet("https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source"))()
wait(3)
return {loaded = true, message = "Infinite Yield loaded. You can now use execute_iy."}
"""
        return await send_lua(code)

    elif name == "execute_iy":
        cmd = args["command"]
        code = f"""
if not IY_LOADED then
    loadstring(game:HttpGet("https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source"))()
    wait(3)
end
execCmd("{_escape(cmd)}", game:GetService("Players").LocalPlayer, true)
return {{executed = "{_escape(cmd)}"}}
"""
        return await send_lua(code)

    else:
        return {"error": f"Unknown tool: {name}"}


async def main():
    global WS_PORT
    print(f"[MCP] Starting WebSocket server on {WS_HOST}:{WS_PORT}...", file=sys.stderr)
    try:
        ws_server = await ws_serve(ws_handler, WS_HOST, WS_PORT)
    except OSError as e:
        print(f"[MCP] Port {WS_PORT} in use, trying {WS_PORT + 1}...", file=sys.stderr)
        WS_PORT += 1
        ws_server = await ws_serve(ws_handler, WS_HOST, WS_PORT)
    print(f"[MCP] WebSocket server active on {WS_HOST}:{WS_PORT}. Waiting for Roblox connection...", file=sys.stderr)

    async with stdio_server() as (read, write):
        print(f"[MCP] MCP server started", file=sys.stderr)
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

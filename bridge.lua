local PORTS = {9876, 9877}
local HttpService = game:GetService("HttpService")

local ws, connected = false

local function serialize(value)
    local ok, result = pcall(HttpService.JSONEncode, HttpService, value)
    if ok then return result end
    return HttpService:JSONEncode(tostring(value))
end

local function on_message(message)
    local data = HttpService:JSONDecode(message)
    local ok, result = pcall(function()
        local fn, err = loadstring(data.code)
        if not fn then error("Compile error: " .. tostring(err)) end
        return fn()
    end)
    local resp = ok and {id=data.id, type="result", value=result}
                   or {id=data.id, type="error", error=tostring(result)}
    local enc = serialize(resp)
    if enc then ws:Send(enc) end
end

local function try_connect()
    for _, port in PORTS do
        local ok, sock = pcall(WebSocket.connect, "ws://localhost:" .. port)
        if ok and sock then
            ws = sock
            if not connected then
                connected = true
                rconsoleinfo([[

    [OK] CONNECTED TO SERVER
]])
            end
            ws.OnMessage:Connect(on_message)
            ws.OnClose:Connect(function()
                connected = false
                rconsolewarn("\n   [!] Disconnected - Reconnecting...\n")
                task.wait(3)
                try_connect()
            end)
            return
        end
    end
    task.wait(5)
    try_connect()
end

rconsolecreate()
rconsoleclear()
rconsolesettitle("ESENCIA X - MCP Bridge")

rconsolewarn([[

    ================================================
    =                                              =
    =                                              =
    =]])
rconsoleerror([[              E S E N C I A   X              ]])
rconsolewarn([[
    =]])
rconsoleinfo([[          M C P    B R I D G E               ]])
rconsolewarn([[
    =]])
rconsoleprint([[                v 2 . 0                       ]])
rconsolewarn([[
    =                                              =
    =                                              =
    ================================================

]])
rconsoleinfo([[

       >> Connecting to MCP server...
]])
try_connect()

import asyncio
from decimal import Decimal
from aiohttp.web import (
    Application,
    Request,
    Response,
    StreamResponse,
    get,
    run_app,
    WebSocketResponse,
)
from aiohttp_sse import sse_response


async def web_streaming(request: Request):
    print("Hello")
    response = StreamResponse()
    response.content_type = "text/html"
    await response.prepare(request)

    text = """
<html>
<head></head>
<body>
<div>
Loading, please wait...
</div>
<ul>
<li>Step 1: Make a slow website</li>
<li>Step 2: Stream it with HTTP</li>
<li>Step 3: ???</li>
<li>Step 4: Profit!</li>
</ul>
</body>
<html>
"""

    for t in text.split("\n"):
        b = bytearray(t + "\n", "utf-8")
        await response.write(b)
        await asyncio.sleep(0.75)
    return response


# Adapted from https://www.wikihow.com/Write-a-Python-Program-to-Calculate-Pi
def nilakantha(reps):
    result = Decimal(3.0)
    op = 1
    n = 2
    for n in range(2, 2 * reps + 1, 2):
        result += 4 / Decimal(n * (n + 1) * (n + 2) * op)
        op *= -1
        yield result
    return result


async def pi(request: Request):
    response = StreamResponse()
    response.content_type = "text/html"
    await response.prepare(request)

    for i, pi in enumerate(nilakantha(100000000)):
        ITER_SIZE = 1000000
        if i % ITER_SIZE == 0:
            b = bytearray(
                f"<div id='i_{i}'>Pi after {i} iterations is {pi}</div><style>div#i_{i - ITER_SIZE} "
                + "{display: none;} </style>\n\n",
                "utf-8",
            )
            await response.write(b)
    return response


messages = {}


async def server_sent_events(request: Request):
    my_name = request.match_info["name"]
    try:
        # Alert everyone that you are online!
        for queue in messages.values():
            await queue.put(my_name + " is now online!")

        messages[my_name] = asyncio.Queue(100)

        async with sse_response(request) as resp:
            # Listen for messages and send it to the user
            while True:
                try:
                    await resp.send(messages[my_name].get_nowait())
                except asyncio.QueueEmpty:
                    if resp._ping_task.done():
                        break
                    await asyncio.sleep(0.1)
    except (asyncio.CancelledError, ConnectionResetError, KeyError):
        pass
    finally:
        # Alert everyone that you are now offline
        if my_name in messages:
            del messages[my_name]
        for queue in messages.values():
            asyncio.create_task(queue.put(my_name + " is now offline!"))


connected_sockets = {}


async def websockets(request: Request):
    my_name = request.match_info["name"]

    ws = WebSocketResponse()
    await ws.prepare(request)
    connected_sockets[my_name] = ws

    # On Connect
    for socket in connected_sockets.values():
        await socket.send_str(f"{my_name} has joined the chat")

    # Relay messages
    async for message in ws:
        for socket in connected_sockets.values():
            await socket.send_str(f"{my_name}: {message.data}")

    # On Disconnect
    if my_name in connected_sockets:
        del connected_sockets[my_name]
    for socket in connected_sockets.values():
        asyncio.create_task(socket.send_str(f"{my_name} has left the chat"))


async def chat(request: Request):
    my_name = request.match_info["name"]
    with open("chat.html", "r") as f:
        return Response(
            body=f.read().replace("{name}", my_name), content_type="text/html"
        )


app = Application()
app.add_routes(
    [
        get("/stream", web_streaming),
        get("/pi", pi),
        get("/sse/{name}", server_sent_events),
        get("/ws/{name}", websockets),
        get("/chat/{name}", chat),
    ]
)
run_app(app, port=7890)

import asyncio
import websockets
from websockets.asyncio.server import *
from aiohttp import web
from PIL import ImageGrab
import io
import logging
import platform
import socket

# Configuration
HTTP_PORT = 8100
WS_PORT = 8099
INTERVAL_SECONDS = 1
RESIZE_SCALE = 0.6  # Scale down screenshot to 60% of original size

# Set up logging
logging.basicConfig(level=logging.FATAL, format='%(asctime)s %(levelname)s:%(message)s')

# Store WebSocket clients
clients = set()

# Serve the webpage on port 8100
async def index(request):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hub and Disc Application Stream</title>
    </head>
    <body>
        <h2>Hub and Disc Application Stream</h2>
        <img id="screenshot" style="max-width:100%; border:1px solid black" />
        <script>
            const img = document.getElementById('screenshot');
            const ws = new WebSocket('ws://' + window.location.hostname + ':8099');

            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                console.log('WebSocket connected');
            };

            ws.onmessage = (event) => {
                console.log('Received data size:', event.data.byteLength, 'bytes');
                const blob = new Blob([event.data], {type: 'image/jpeg'});
                const url = URL.createObjectURL(blob);
                img.onload = () => {
                    URL.revokeObjectURL(url); // Revoke after image loads
                };
                img.src = url;
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
            };

            ws.onclose = () => {
                console.log('WebSocket connection closed');
            };
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def serve_webpage(port):
    app = web.Application()
    app.router.add_get('/', index)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', port)
    await site.start()
    logging.info(f'HTTP server started at http://127.0.0.1:{port}')

# WebSocket handler for sending screenshots
async def screenshot_websocket(websocket: ServerConnection):
    logging.info(f'Websockets Type is: {type(websocket)}')
    logging.debug(f'Received WebSocket connection with path: {websocket.request.path}')
    logging.info(f'Client connected: {websocket.remote_address}')
    clients.add(websocket)
    try:
        while True:
            try:
                # Check platform
                if platform.system() not in ['Windows', 'Darwin']:
                    logging.error('ImageGrab is supported only on Windows and macOS')
                    break
                # Capture and resize screenshot
                screenshot = ImageGrab.grab()
                new_size = (int(screenshot.width * RESIZE_SCALE), int(screenshot.height * RESIZE_SCALE))
                screenshot = screenshot.resize(new_size)
                buf = io.BytesIO()
                screenshot.save(buf, format='JPEG', quality=85)  # Save as JPEG
                data = buf.getvalue()
                # Send only image data
                await websocket.send(data)
                logging.debug(f'Sent screenshot of size {len(data)} bytes to {websocket.remote_address}')
            except Exception as e:
                logging.error(f'Error capturing or sending screenshot: {e}')
            await asyncio.sleep(INTERVAL_SECONDS)
    except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError, asyncio.CancelledError):
        logging.info(f'Client disconnected: {websocket.remote_address}')
    finally:
        clients.discard(websocket)  # Use discard to avoid KeyError if already removed

def find_free_port(start_port):
    port = start_port
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                s.listen(1)
                logging.info(f'Found free port: {port}')
                return port
        except OSError:
            logging.debug(f'Port {port} in use, trying next')
            port += 1

async def main():
    # Find free ports
    http_port = find_free_port(HTTP_PORT)
    ws_port = find_free_port(WS_PORT)

    # Start HTTP server
    http_task = asyncio.create_task(serve_webpage(http_port))

    # Start WebSocket server
    logging.debug(f'Registering WebSocket handler: {screenshot_websocket.__name__}')
    ws_server = await websockets.serve(screenshot_websocket, '127.0.0.1', ws_port)
    logging.info(f'WebSocket server started at ws://127.0.0.1:{ws_port}')
    print(f'Show Screen server started at http://127.0.0.1:{HTTP_PORT}')

    # Run forever
    await asyncio.gather(http_task, ws_server.wait_closed())

def showScreen():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Server stopped by user')
    except Exception as e:
        logging.exception(f'Unexpected error: {e}')

def startTheShowScreenService():
    showScreen()
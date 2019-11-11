import asyncio
import time
import subprocess
import select
import websockets

class LogTailer():
    def __init__(self, path, callback):
        self.path = path
        self.callback = callback
        self.should_tail = True

    async def tail(self):
        tailer = subprocess.Popen(['tail', '-F', self.path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        poller = select.poll()
        poller.register(tailer.stdout)

        while self.should_tail:
            if poller.poll(1):
                line = f.stdout.readline().decode("utf-8")
                line = line.replace("\n", "")

                await self.callback(line)
            else:
                time.sleep(0.05)

class WebsocketConnection():
    def __init__(self):
        self.websocket_uri = "wss://"
        self.websocket = websockets.connect(self.websocket_uri)

    async def broadcast_line(self, line):
        print("Sending: {}".format(line))
        await self.websocket.send(line)

socket = WebsocketConnection()

tailer = LogTailer("/Users/v-brandon.sturgeon/Code/personal/cfc_rcon_reader/test/output.log", socket.broadcast_line)

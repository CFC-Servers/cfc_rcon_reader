import os
import select
import sentry_sdk
import subprocess
import time
import threading

from dotenv import load_dotenv
from lib.actioncable.connection import Connection
from lib.actioncable.subscription import Subscription
from lib.actioncable.message import Message

class LogTailer():
    def __init__(self, path, interval=0.35):
        self.path = path
        self.should_tail = False
        self.callbacks = []
        self.last_run = time.time()
        self.run_interval = interval
        self.line_queue = []

        self.runner_thread = threading.Thread(target=self.runner)

    def start(self):
        self.should_tail = True
        self.runner_thread.start()
        self.tail()

    def stop(self):
        self.should_tail = False
        self.runner_thread.stop()

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def run_callbacks(self):
        [cb(self.line_queue) for cb in self.callbacks]
        self.last_run = time.time()

    def time_to_run(self):
        return time.time() - self.last_run >= self.run_interval

    def queue_too_big(self):
        return len(self.line_queue) > 30

    def make_tailer(self):
        return subprocess.Popen(['tail', '-F', '-n', '1', self.path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def make_poller(self, tailer):
        poller = select.poll()
        poller.register(tailer.stdout)

        return poller

    def clean_line(self, line):
        line = line.decode("utf-8")
        line = line.replace("\n", "")

        return line

    def queue_line(self, line):
        self.line_queue.append(line)

    def clear_line_queue(self):
        self.line_queue = []

    def queue_is_empty(self):
        return len(self.line_queue) == 0

    def should_queue_line(self, line):
        if len(line.strip()) == 0:
            return False

        return True

    def should_run_callbacks(self):
        has_items = not self.queue_is_empty()
        is_expired = self.time_to_run()
        queue_too_big = self.queue_too_big()

        return (has_items and is_expired) or queue_too_big

    def runner(self):
        print("Starting callback runner thread...")
        while self.should_tail:
            if self.should_run_callbacks():
                self.run_callbacks()
                self.clear_line_queue()

            time.sleep(self.run_interval/2)

    def tail(self):
        tailer = self.make_tailer()
        poller = self.make_poller(tailer)

        while self.should_tail:
            line = tailer.stdout.readline()
            line = self.clean_line(line)

            print("Got new line: {}".format(line))

            if self.should_queue_line(line):
                self.queue_line(line)

class ActionCableInterface():
    def __init__(self, channel_name, action, websocket_api_key, websocket_uri, websocket_origin):
        self.channel_name = channel_name
        self.action = action
        self.websocket_api_key = websocket_api_key
        self.websocket_uri = websocket_uri
        self.websocket_origin = websocket_origin

        tokenized_uri = "{}?token={}".format(self.websocket_uri, self.websocket_api_key)
        connection = Connection(url=tokenized_uri, origin=self.websocket_origin)
        connection.connect()

        identifier = {"channel": self.channel_name}

        self.subscription = Subscription(connection, identifier=identifier)
        self.subscription.logger.setLevel("ERROR")
        self.subscription.create()

        print("Created actioncable subscription")

    def send_lines(self, lines):
        data = {
            "lines": lines,
            "token": self.websocket_api_key
        }

        message = Message(action=self.action, data=data)
        self.subscription.send(message)

if __name__ == "__main__":
    load_dotenv()

    sentry_sdk.init(
        os.getenv("SENTRY_DSN"),
        traces_sample_rate=1.0,
        environment=os.getenv("SENTRY_ENVIRONMENT")
    )

    channel_name = os.getenv("CHANNEL_NAME")
    action = os.getenv("WEBSOCKET_ACTION")
    websocket_api_key = os.getenv("WEBSOCKET_API_KEY")
    websocket_uri = os.getenv("WEBSOCKET_URI")
    websocket_origin = os.getenv("WEBSOCKET_ORIGIN")
    log_file = os.getenv("LOG_FILE_PATH")

    action_cable = ActionCableInterface(
        channel_name, action, websocket_api_key, websocket_uri, websocket_origin
    )

    tailer = LogTailer(log_file)
    tailer.add_callback(action_cable.send_lines)

    tailer.start()

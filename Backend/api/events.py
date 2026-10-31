"""Thread-safe delivery of backend notifications to WebSocket clients."""


class EventHub:
    """Bounded per-connection queues; disconnect slow peers so they resync."""
    def __init__(self):
        self.clients = set()
        self.loop = None

    def publish(self, message):
        if self.loop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._publish, message)

    def _publish(self, message):
        for queue in tuple(self.clients):
            if queue.full():
                self.clients.discard(queue)
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait({"type": "resync"})
            else:
                queue.put_nowait(message)

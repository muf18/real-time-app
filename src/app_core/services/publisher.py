import asyncio
from typing import Any, Set


class Publisher:
    """A simple asyncio-based fan-out publisher."""
    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Adds a new subscriber and returns the queue for it."""
        queue = asyncio.Queue()
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Removes a subscriber."""
        self.subscribers.discard(queue)

    async def publish(self, message: Any):
        """Publishes a message to all subscribers."""
        for queue in self.subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Handle backpressure if necessary, e.g., log a warning
                # For this real-time app, we prefer dropping if UI can't keep up.
                pass


# Create singleton instances for different data types
raw_trade_publisher = Publisher()
aggregated_data_publisher = Publisher()
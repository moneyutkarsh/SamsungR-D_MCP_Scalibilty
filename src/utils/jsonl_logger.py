import json
import asyncio
from datetime import datetime, timezone
import os

class JSONLLogger:
    def __init__(self, path: str):
        self.path = path
        self.queue = asyncio.Queue()
        self._worker_task = None

    async def log(self, obj: dict):
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())

        # Timezone-aware UTC timestamp (research-grade)
        obj["timestamp"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(obj) + "\n"
        
        # Non-blocking queue put
        self.queue.put_nowait(line)

    async def _worker(self):
        # Background task that flushes the queue to disk
        while True:
            # Wait for the first item
            line = await self.queue.get()
            batch = [line]
            self.queue.task_done()
            
            # Greedily pull any other pending items to batch write
            while not self.queue.empty():
                try:
                    batch.append(self.queue.get_nowait())
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break
                    
            # Offload the batched disk write to a single thread
            try:
                await asyncio.to_thread(self._write_batch, batch)
            except Exception as e:
                print(f"Error writing to JSONL log {self.path}: {e}")

    def _write_batch(self, batch: list[str]):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.writelines(batch)

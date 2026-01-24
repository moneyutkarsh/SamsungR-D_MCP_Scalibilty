import json
import asyncio
from datetime import datetime, timezone

class JSONLLogger:
    def __init__(self, path: str):
        self.path = path

    async def log(self, obj: dict):
        # Timezone-aware UTC timestamp (research-grade)
        obj["timestamp"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(obj) + "\n"

        # Offload blocking disk I/O to thread pool
        await asyncio.to_thread(self._write_line, line)

    def _write_line(self, line: str):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)

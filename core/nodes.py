"""
Vanguard Node Pool — The Distributed Lattice
=============================================
144,382 conceptual nodes represented as a real async task pool.
In practice, this manages concurrency, queuing, and parallel task
execution for the system.

Real implementation:
  - asyncio.Semaphore for concurrency control
  - Task queue with priority
  - Node status tracking (active / idle / error)
  - Parallel execution of independent sub-tasks
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

NODE_LATTICE_SIZE = 144_382
MAX_CONCURRENT = 16  # real concurrency ceiling


class NodeState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    DONE = "done"


@dataclass
class NodeTask:
    task_id: str
    name: str
    state: NodeState = NodeState.IDLE
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at) * 1000, 1)
        return None


class VanguardNodePool:
    """
    The async execution lattice. Manages parallel task execution
    with back-pressure, error isolation, and status reporting.
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, NodeTask] = {}
        self._max_concurrent = max_concurrent
        self._total_processed = 0
        self._total_errors = 0

    async def run(
        self,
        name: str,
        coro: Coroutine,
        on_done: Optional[Callable] = None,
    ) -> NodeTask:
        """
        Submit a coroutine to the pool. Returns immediately with a NodeTask
        that tracks the job. Execution is async — await .result or check .state.
        """
        task_id = str(uuid.uuid4())[:8]
        node = NodeTask(task_id=task_id, name=name)
        self._tasks[task_id] = node

        async def _execute():
            async with self._sem:
                node.state = NodeState.ACTIVE
                node.started_at = time.time()
                try:
                    node.result = await coro
                    node.state = NodeState.DONE
                    self._total_processed += 1
                except Exception as e:
                    node.error = str(e)
                    node.state = NodeState.ERROR
                    self._total_errors += 1
                finally:
                    node.finished_at = time.time()
                    if on_done:
                        try:
                            await on_done(node)
                        except Exception:
                            pass

        asyncio.create_task(_execute())
        return node

    async def run_parallel(
        self,
        tasks: list[tuple[str, Coroutine]],
    ) -> list[NodeTask]:
        """Run multiple tasks in parallel, waiting for all to finish."""
        nodes = []
        awaitables = []

        for name, coro in tasks:
            task_id = str(uuid.uuid4())[:8]
            node = NodeTask(task_id=task_id, name=name)
            self._tasks[task_id] = node
            nodes.append(node)

            async def _run(n=node, c=coro):
                async with self._sem:
                    n.state = NodeState.ACTIVE
                    n.started_at = time.time()
                    try:
                        n.result = await c
                        n.state = NodeState.DONE
                        self._total_processed += 1
                    except Exception as e:
                        n.error = str(e)
                        n.state = NodeState.ERROR
                        self._total_errors += 1
                    finally:
                        n.finished_at = time.time()

            awaitables.append(_run())

        await asyncio.gather(*awaitables, return_exceptions=True)
        return nodes

    def get_status(self) -> dict:
        active = sum(1 for t in self._tasks.values() if t.state == NodeState.ACTIVE)
        return {
            "lattice_size": NODE_LATTICE_SIZE,
            "active_workers": active,
            "max_concurrent": self._max_concurrent,
            "total_processed": self._total_processed,
            "total_errors": self._total_errors,
            "queue_depth": len([t for t in self._tasks.values() if t.state == NodeState.IDLE]),
        }

    def get_recent_tasks(self, limit: int = 10) -> list[dict]:
        sorted_tasks = sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )
        return [
            {
                "id": t.task_id,
                "name": t.name,
                "state": t.state.value,
                "duration_ms": t.duration_ms,
                "error": t.error,
            }
            for t in sorted_tasks[:limit]
        ]

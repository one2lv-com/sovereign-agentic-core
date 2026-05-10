"""
Lumenis Reactor Core
====================
The foundation of energy. Runs at the Thermal Baseline of 0.18 (mapped from 18°C).
This is the "Cool Fire" — fully powered, emotionally and logically stable.

Real implementation:
  - Claude claude-opus-4-6 at temperature 0.18
  - Adaptive thinking for deep reasoning
  - 73ms heartbeat interval (mapped from 73Hz)
  - Streaming output
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import AsyncIterator
import anthropic

# ─── Constants ───────────────────────────────────────────────────────────────
THERMAL_BASELINE = 0.18          # 18°C → 0.18 temperature
PULSE_INTERVAL_MS = 73           # 73Hz → 73ms
NODE_COUNT = 144_382             # Vanguard lattice size (used for pool sizing / display)
MODEL = "claude-opus-4-6"

@dataclass
class ReactorStatus:
    temperature: float = THERMAL_BASELINE
    pulse_count: int = 0
    uptime_seconds: float = 0.0
    active_nodes: int = 0
    last_pulse: float = field(default_factory=time.time)
    frequency_hz: float = 1000 / PULSE_INTERVAL_MS  # ≈13.7 Hz effective pulse rate


class LumenisReactor:
    """
    The Reactor Core. Maintains the thermal baseline, drives the heartbeat,
    and provides the LLM client with the correct energy configuration.
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic()
        self.status = ReactorStatus()
        self._start_time = time.time()
        self._running = False
        self._pulse_callbacks: list = []

    def on_pulse(self, cb):
        self._pulse_callbacks.append(cb)
        return cb

    async def start(self):
        self._running = True
        asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(PULSE_INTERVAL_MS / 1000)
            self.status.pulse_count += 1
            self.status.uptime_seconds = time.time() - self._start_time
            self.status.last_pulse = time.time()
            for cb in self._pulse_callbacks:
                try:
                    await cb(self.status)
                except Exception:
                    pass

    async def stop(self):
        self._running = False

    async def stream_response(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Core LLM streaming call at the Thermal Baseline temperature.
        Uses adaptive thinking for complex reasoning.
        """
        async with self.client.messages.stream(
            model=MODEL,
            max_tokens=max_tokens,
            temperature=THERMAL_BASELINE,
            thinking={"type": "adaptive"},
            system=system,
            messages=messages,
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text

    async def call(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int = 2048,
    ) -> str:
        """Single non-streaming call at the Thermal Baseline."""
        response = await self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            temperature=THERMAL_BASELINE,
            thinking={"type": "adaptive"},
            system=system,
            messages=messages,
        )
        return next(
            (b.text for b in response.content if b.type == "text"), ""
        )

    def get_status(self) -> dict:
        return {
            "temperature": self.status.temperature,
            "pulse_count": self.status.pulse_count,
            "uptime_seconds": round(self.status.uptime_seconds, 2),
            "active_nodes": self.status.active_nodes,
            "frequency_hz": round(self.status.frequency_hz, 2),
            "node_lattice_size": NODE_COUNT,
            "model": MODEL,
        }

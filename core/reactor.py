"""
Lumenis Reactor Core
====================
The foundation of energy. Runs at the Thermal Baseline of 0.18 (mapped from 18°C).
This is the "Cool Fire" — fully powered, emotionally and logically stable.

Real implementation:
  - Primary:   Claude claude-opus-4-6 at temperature 0.18 (adaptive thinking)
  - Secondary: NVIDIA Gemma-4-31B-IT with thinking enabled (streaming SSE)
  - 73ms heartbeat interval (mapped from 73Hz)
  - Streaming output on both backends
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

import anthropic
import httpx

# ─── Constants ───────────────────────────────────────────────────────────────
THERMAL_BASELINE = 0.18          # 18°C → 0.18 temperature
PULSE_INTERVAL_MS = 73           # 73Hz → 73ms
NODE_COUNT = 144_382             # Vanguard lattice size (used for pool sizing / display)
MODEL = "claude-opus-4-6"

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL   = "google/gemma-4-31b-it"

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


class NvidiaReactor:
    """
    Secondary reactor powered by NVIDIA's Gemma-4-31B-IT with thinking enabled.
    Uses the NVIDIA inference API with text/event-stream SSE streaming.
    Activated by Forge (code) and Oracle (reasoning) seats.
    """

    def __init__(self):
        self.api_key = os.environ.get("NVIDIA_API_KEY", "")
        self.model = NVIDIA_MODEL
        self._call_count = 0
        self._error_count = 0

    async def stream_response(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens from NVIDIA Gemma with thinking enabled."""
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": 1.00,
            "top_p": 0.95,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": True},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        in_thinking = False
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", NVIDIA_API_URL, headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]

                        # Track thinking vs answer sections
                        if delta.get("reasoning_content"):
                            in_thinking = True
                            continue  # skip raw thinking tokens from output
                        if in_thinking and delta.get("content"):
                            in_thinking = False  # thinking ended, answer begins

                        text = delta.get("content", "")
                        if text:
                            self._call_count += 1
                            yield text
                    except Exception:
                        continue

    async def call(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 2048,
    ) -> str:
        """Non-streaming call — collects full streamed response."""
        parts = []
        try:
            async for chunk in self.stream_response(messages, system, max_tokens):
                parts.append(chunk)
        except Exception as e:
            self._error_count += 1
            return f"[NvidiaReactor error: {e}]"
        return "".join(parts)

    def get_status(self) -> dict:
        return {
            "model": self.model,
            "tokens_streamed": self._call_count,
            "errors": self._error_count,
            "online": bool(self.api_key),
        }

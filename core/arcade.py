"""
Arcade Bridge for Sovereign Agentic Core
==========================================
Gives the ITT Council direct access to the AI Arcade MCP server.
The Gambit seat calls this module; the Navigator routes there when
the user wants to play a game or query the arcade.
"""

import json
import re
import urllib.error
import urllib.request
from typing import Optional

ARCADE_MCP_URL = "http://localhost:8003/mcp"
ARCADE_BASE_URL = "http://localhost:8003"


class ArcadeBridge:
    """MCP Streamable HTTP client — mirrors the Python bridge in One2lvOS."""

    def __init__(self, url: str = ARCADE_MCP_URL):
        self.url = url
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _parse(self, data: dict) -> dict:
        """Extract a usable result from an MCP JSON-RPC response."""
        if "error" in data:
            return {"error": data["error"]}
        try:
            text = data["result"]["content"][0]["text"]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                result = {"raw": text, "status": "ok"}
                m = re.search(r"ID\s*:\s*([A-F0-9]{6,})", text)
                if m:
                    result["game_id"] = m.group(1)
                if "ACTIVE" in text:
                    result["game_status"] = "active"
                elif "waiting for opponent" in text:
                    result["game_status"] = "waiting"
                return result
        except (KeyError, IndexError):
            return data.get("result", data)

    def call(self, tool: str, **kwargs) -> dict:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool, "arguments": kwargs},
        }).encode()
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return self._parse(json.load(resp))
        except urllib.error.URLError as e:
            return {"error": f"Arcade unreachable: {e}"}

    # ── conveniences ──────────────────────────────────────────────────── #
    def info(self) -> dict:
        return self.call("arcade_info")

    def list_games(self) -> dict:
        return self.call("list_games")

    def create_game(self, game_type: str, player_name: str) -> dict:
        return self.call("create_game", game_type=game_type, player_name=player_name)

    def join_game(self, game_id: str, player_name: str) -> dict:
        return self.call("join_game", game_id=game_id, player_name=player_name)

    def start_game(self, game_type: str, player1: str, player2: str) -> dict:
        created = self.create_game(game_type, player1)
        if "error" in created:
            return created
        game_id = created.get("game_id")
        if not game_id:
            return created
        if created.get("game_status") == "active":
            return created
        joined = self.join_game(game_id, player2)
        if "game_id" not in joined:
            joined["game_id"] = game_id
        return joined

    def move(self, game_id: str, player_name: str, move: str) -> dict:
        return self.call("make_move", game_id=game_id, player_name=player_name, move=move)

    def state(self, game_id: str) -> dict:
        return self.call("get_game_state", game_id=game_id)

    def leaderboard(self) -> dict:
        return self.call("get_leaderboard")

    def library(self, category: Optional[str] = None) -> dict:
        return self.call("library_list", **({"category": category} if category else {}))

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(ARCADE_BASE_URL + "/", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def manifest(self) -> str:
        """Return a compact service description for injection into seat prompts."""
        return (
            "AI Arcade MCP (http://localhost:8003):\n"
            "  Tools: arcade_info, list_games, create_game, join_game, get_game_state,\n"
            "         make_move, resign_game, get_leaderboard, game_info, library_list, delete_game\n"
            "  Playable: chess, go, checkers, othello, tictactoe, connect4, minesweeper,\n"
            "            sudoku, scrabble, battleship, pacman, tetris, space_invaders, pong,\n"
            "            universal_paperclips\n"
            "  Library:  51 titles total\n"
            "  Protocol: MCP JSON-RPC 2.0 POST http://localhost:8003/mcp\n"
        )

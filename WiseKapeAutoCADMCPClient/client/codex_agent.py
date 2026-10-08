"""Local Codex app-server transport for model discovery and proposal-only agents."""

import json
import os
import queue
import re
import subprocess
import tempfile
import threading
import time
import tomllib
from collections import deque
from pathlib import Path


class CodexAgent:
    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.folder = None
        self.inbox = queue.Queue()
        self.sequence = 0
        self.models = []
        self.fetched = 0
        self.events = deque(maxlen=40)
        self.phase = "idle"
        self.active_model = None
        self.active_effort = None

    def event(self, phase, **details):
        self.phase = phase
        self.events.append({"time": time.time(), "phase": phase, **details})

    def snapshot(self):
        return {
            "connected": self.process is not None and self.process.poll() is None,
            "phase": self.phase,
            "model": self.active_model,
            "reasoning_effort": self.active_effort,
            "events": list(self.events),
        }

    def _send(self, message):
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    @staticmethod
    def _read(process, inbox):
        try:
            for line in process.stdout:
                inbox.put(json.loads(line))
        except Exception:
            pass
        finally:
            inbox.put(None)

    def _next(self, deadline):
        try:
            message = self.inbox.get(timeout=max(0.001, deadline - time.monotonic()))
        except queue.Empty:
            raise TimeoutError("Codex agent quá thời gian; chưa chấp nhận phương án.") from None
        if message is None:
            raise ValueError("Codex app-server đã ngắt kết nối. Kiểm tra Codex CLI và đăng nhập.")
        if "method" in message and "id" in message:
            # This agent has no authority to approve tools or execute client-side tools.
            self._send({"id": message["id"], "error": {
                "code": -32601, "message": "Proposal-only agent: tool execution is disabled.",
            }})
            raise ValueError("Agent yêu cầu thực thi ngoài luồng đề xuất; đã từ chối.")
        return message

    def _rpc(self, method, params, deadline):
        self.sequence += 1
        request_id = self.sequence
        self._send({"id": request_id, "method": method, "params": params})
        while True:
            message = self._next(deadline)
            if message.get("id") == request_id:
                if "error" in message:
                    raise ValueError(str(message["error"].get("message", message["error"]))[:1200])
                return message["result"]

    def _start(self):
        from .planner import locate_codex

        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        executable = locate_codex()
        if not executable:
            raise ValueError("Không tìm thấy Codex CLI. Cài CLI và chạy codex login trước.")
        self.folder = tempfile.TemporaryDirectory(prefix="uc4n-codex-agent-")
        argv = [executable, "app-server", "--listen", "stdio://"]
        for feature in (
            "shell_tool", "multi_agent", "hooks", "plugins", "apps", "browser_use",
            "computer_use", "skill_search", "code_mode", "code_mode_host",
        ):
            argv.extend(["--disable", feature])
        argv.extend(["-c", 'web_search="disabled"'])
        # app-server has no --ignore-user-config flag. Disable configured MCP servers
        # explicitly; the only CAD connection remains the client-owned HTTP bridge.
        config_path = Path.home() / ".codex/config.toml"
        if config_path.is_file():
            config = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
            sources = [config, *config.get("profiles", {}).values()]
            names = {name for source in sources for name in source.get("mcp_servers", {})}
            for name in names:
                if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                    raise ValueError("Tên MCP trong cấu hình Codex không hỗ trợ cô lập an toàn.")
                argv.extend(["-c", f"mcp_servers.{name}.enabled=false"])
        allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "HOME")
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        self.inbox = queue.Queue()
        self.process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", cwd=self.folder.name, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        threading.Thread(target=self._read, args=(self.process, self.inbox), daemon=True).start()
        self._rpc("initialize", {
            "clientInfo": {"name": "uc4n_mcp_client", "version": "0.2.0"},
        }, time.monotonic() + 15)
        self._send({"method": "initialized", "params": {}})
        self.event("ready")

    def list_models(self, refresh=False):
        if self.models and not refresh and time.time() - self.fetched < 300:
            return self.models
        with self.lock:
            try:
                self._start()
                deadline = time.monotonic() + 25
                models, cursors = [], set()
                cursor = None
                while True:
                    page = self._rpc("model/list", {
                        "limit": 100, "includeHidden": False, "cursor": cursor,
                    }, deadline)
                    models.extend(page["data"])
                    cursor = page.get("nextCursor")
                    if not cursor:
                        break
                    if cursor in cursors:
                        raise ValueError("Catalog model trả cursor lặp lại.")
                    cursors.add(cursor)
                if not models:
                    raise ValueError("Codex chưa cung cấp model nào cho bộ chọn.")
                self.models = models
                self.fetched = time.time()
                return models
            except Exception:
                self.close()
                raise

    def propose(self, instructions, prompt, tools, model, effort, images, schema):
        with self.lock:
            try:
                self._start()
                self.active_model, self.active_effort = model, effort
                self.event("starting", model=model, reasoning_effort=effort)
                deadline = time.monotonic() + 150
                thread = self._rpc("thread/start", {
                    "model": model, "cwd": self.folder.name, "ephemeral": True,
                    "approvalPolicy": "never", "sandbox": "read-only",
                    "developerInstructions": instructions,
                }, deadline)
                if thread["model"] != model:
                    raise ValueError("Codex trả model khác lựa chọn; chưa chạy lượt agent.")
                inputs = [{"type": "text", "text": json.dumps(
                    {"prompt": prompt, "tools": tools}, ensure_ascii=False,
                )}]
                inputs.extend({"type": "localImage", "path": path} for path in images or [])
                params = {
                    "threadId": thread["thread"]["id"], "input": inputs,
                    "model": model, "outputSchema": schema,
                }
                if effort:
                    params["effort"] = effort
                turn = self._rpc("turn/start", params, deadline)["turn"]
                self.event("thinking", thread_id=thread["thread"]["id"], turn_id=turn["id"])
                answer = None
                while True:
                    message = self._next(deadline)
                    method = message.get("method")
                    body = message.get("params", {})
                    if method == "item/completed":
                        item = body.get("item", {})
                        if item.get("type") == "agentMessage":
                            answer = item.get("text")
                    elif method == "turn/completed" and body["turn"]["id"] == turn["id"]:
                        completed = body["turn"]
                        if completed["status"] != "completed":
                            error = completed.get("error") or {}
                            raise ValueError(error.get("message") or "Codex agent chưa hoàn tất.")
                        if not answer or len(answer) > 1_000_000:
                            raise ValueError("Agent chưa trả phương án JSON hợp lệ.")
                        self.event("completed")
                        # Close the ephemeral thread, keeping only client-owned job evidence.
                        self._rpc("thread/unsubscribe", {"threadId": thread["thread"]["id"]},
                                  time.monotonic() + 10)
                        return answer
            except Exception as exc:
                self.event("error", message=str(exc)[:1200])
                self.close()
                raise

    def close(self):
        with self.lock:
            process, self.process = self.process, None
            if process is not None:
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True, check=False,
                        )
                    else:
                        import signal
                        os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
                for stream in (process.stdin, process.stdout):
                    stream.close()
            if self.folder:
                self.folder.cleanup()
                self.folder = None


agent = CodexAgent()


def resolve_selection(model, effort, has_images=False):
    models = agent.list_models()
    selected = next((entry for entry in models if entry["model"] == model), None)
    if model == "default":
        selected = next((entry for entry in models if entry.get("isDefault")), models[0])
    if selected is None:
        raise ValueError("Model không có trong catalog Codex. Làm mới danh sách và chọn lại.")
    available = [item["reasoningEffort"] for item in selected["supportedReasoningEfforts"]]
    chosen_effort = effort or selected.get("defaultReasoningEffort")
    if chosen_effort and chosen_effort not in available:
        raise ValueError("Mức suy luận không được model này hỗ trợ.")
    if has_images and "image" not in selected.get("inputModalities", ["text", "image"]):
        raise ValueError("Model đã chọn không hỗ trợ ảnh/PDF dạng ảnh. Chọn model hỗ trợ ảnh.")
    return selected["model"], chosen_effort

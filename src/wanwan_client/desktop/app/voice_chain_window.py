"""
Minimal tkinter window for manually running the local voice chain.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from src.wanwan_client.desktop.controllers import VoiceChainController


class VoiceChainWindow:
    """Minimal local desktop window that calls VoiceChainController."""

    def __init__(self, controller: VoiceChainController | None = None) -> None:
        self.controller = controller or VoiceChainController()
        self.selected_audio_path = ""
        self.result_queue: queue.Queue[dict[str, Any]] = queue.Queue()

        self.root = tk.Tk()
        self.root.title("Wanwan Voice Chain")
        self.root.geometry("860x700")
        self.root.minsize(720, 560)

        self.selected_audio_var = tk.StringVar(value="未选择音频文件")
        self.trace_id_var = tk.StringVar(value="")
        self.tts_audio_path_var = tk.StringVar(value="")
        self.playback_status_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="请选择一个本地 webm 音频文件。")

        self._build_ui()
        self._apply_optional_auto_close()
        self.root.after(100, self._poll_result_queue)

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(6, weight=1)
        container.rowconfigure(8, weight=1)

        ttk.Label(container, text="本地音频").grid(row=0, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        ttk.Label(
            container,
            textvariable=self.selected_audio_var,
            wraplength=620,
            justify=tk.LEFT,
        ).grid(row=0, column=1, sticky="ew", pady=(0, 8))

        button_row = ttk.Frame(container)
        button_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.select_button = ttk.Button(button_row, text="选择音频", command=self._select_audio_file)
        self.select_button.pack(side=tk.LEFT)

        self.run_button = ttk.Button(button_row, text="运行语音链路", command=self._run_voice_chain)
        self.run_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(container, text="状态").grid(row=2, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        ttk.Label(
            container,
            textvariable=self.status_var,
            wraplength=620,
            justify=tk.LEFT,
        ).grid(row=2, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(container, text="Trace ID").grid(row=3, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        ttk.Label(
            container,
            textvariable=self.trace_id_var,
            wraplength=620,
            justify=tk.LEFT,
        ).grid(row=3, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(container, text="TTS 音频路径").grid(row=4, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        ttk.Label(
            container,
            textvariable=self.tts_audio_path_var,
            wraplength=620,
            justify=tk.LEFT,
        ).grid(row=4, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(container, text="Playback").grid(row=5, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        ttk.Label(
            container,
            textvariable=self.playback_status_var,
            wraplength=620,
            justify=tk.LEFT,
        ).grid(row=5, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(container, text="STT 文本").grid(row=6, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        self.stt_text = ScrolledText(container, height=6, wrap=tk.WORD)
        self.stt_text.grid(row=6, column=1, sticky="nsew", pady=(0, 8))
        self.stt_text.configure(state=tk.DISABLED)

        ttk.Label(container, text="LLM 回复").grid(row=8, column=0, sticky="nw", padx=(0, 12), pady=(0, 8))
        self.llm_text = ScrolledText(container, height=12, wrap=tk.WORD)
        self.llm_text.grid(row=8, column=1, sticky="nsew")
        self.llm_text.configure(state=tk.DISABLED)

    def _select_audio_file(self) -> None:
        initial_dir = Path("data") / "temp"
        selected = filedialog.askopenfilename(
            title="选择本地 webm 音频",
            initialdir=str(initial_dir.resolve()) if initial_dir.exists() else str(Path.cwd()),
            filetypes=[("WebM Audio", "*.webm"), ("All Files", "*.*")],
        )
        if not selected:
            return
        self.selected_audio_path = selected
        self.selected_audio_var.set(selected)
        self.status_var.set("音频已选择，可以运行语音链路。")

    def _run_voice_chain(self) -> None:
        if not self.selected_audio_path:
            self._show_error(
                step="voice_chain",
                error_code="VOICE_CHAIN_AUDIO_PATH_REQUIRED",
                error_message="请先选择一个本地 webm 音频文件。",
                trace_id="",
            )
            return

        self._set_running_state(is_running=True)
        self.status_var.set("正在运行语音链路，请稍候...")
        self.trace_id_var.set("")
        self.tts_audio_path_var.set("")
        self.playback_status_var.set("")
        self._set_text(self.stt_text, "")
        self._set_text(self.llm_text, "")

        worker = threading.Thread(target=self._run_voice_chain_worker, daemon=True)
        worker.start()

    def _run_voice_chain_worker(self) -> None:
        result = self.controller.run(audio_path=self.selected_audio_path)
        self.result_queue.put(result)

    def _poll_result_queue(self) -> None:
        try:
            while True:
                result = self.result_queue.get_nowait()
                self._handle_result(result)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_result_queue)

    def _handle_result(self, result: dict[str, Any]) -> None:
        self._set_running_state(is_running=False)

        trace_id = str(result.get("trace_id") or "")
        self.trace_id_var.set(trace_id)

        if result.get("status") != "success":
            failed_stage = result.get("final", {}).get("failed_stage", {})
            error = failed_stage.get("error", {}) if isinstance(failed_stage, dict) else {}
            self._show_error(
                step=str(failed_stage.get("step") or "voice_chain"),
                error_code=str(error.get("code") or "VOICE_CHAIN_UNKNOWN_ERROR"),
                error_message=str(error.get("message") or "未知错误"),
                trace_id=trace_id,
            )
            return

        final = result.get("final", {})
        stt_text = str(final.get("stt_text") or "")
        llm_reply_text = str(final.get("llm_reply_text") or final.get("reply_text") or "")
        tts_audio_path = str(final.get("tts_audio_path") or "")
        playback = final.get("playback")

        self.status_var.set("语音链路运行成功。")
        self.tts_audio_path_var.set(tts_audio_path)
        self.playback_status_var.set(self._format_playback_status(playback))
        self._set_text(self.stt_text, stt_text)
        self._set_text(self.llm_text, llm_reply_text)

    def _show_error(self, *, step: str, error_code: str, error_message: str, trace_id: str) -> None:
        if trace_id:
            self.trace_id_var.set(trace_id)
        self.status_var.set(f"运行失败 | step={step} | code={error_code} | message={error_message}")
        self.tts_audio_path_var.set("")
        self.playback_status_var.set("failed")
        self._set_text(self.stt_text, "")
        self._set_text(self.llm_text, "")

    def _set_running_state(self, *, is_running: bool) -> None:
        state = tk.DISABLED if is_running else tk.NORMAL
        self.select_button.configure(state=state)
        self.run_button.configure(state=state)

    def _set_text(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state=tk.DISABLED)

    def _format_playback_status(self, playback: Any) -> str:
        if not isinstance(playback, dict):
            return "unknown"
        if playback.get("played") is True:
            return "success"
        if playback.get("played") is False:
            return "failed"
        return "unknown"

    def _apply_optional_auto_close(self) -> None:
        auto_close_ms = os.getenv("WANWAN_DESKTOP_WINDOW_AUTOCLOSE_MS", "").strip()
        if not auto_close_ms:
            return
        try:
            delay = int(auto_close_ms)
        except ValueError:
            return
        if delay > 0:
            self.root.after(delay, self.root.destroy)


def launch_voice_chain_window() -> None:
    """Launch the minimal desktop voice chain window."""
    VoiceChainWindow().run()

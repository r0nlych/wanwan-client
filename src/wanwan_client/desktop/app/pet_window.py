"""
Minimal borderless desktop pet shell built with tkinter.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox

from src.wanwan_client.desktop.controllers import VoiceChainController


class PetWindow:
    """A minimal always-on-top draggable desktop pet shell."""

    WINDOW_SIZE = 160
    BACKGROUND_KEY = "#ff00ff"

    def __init__(self, controller: VoiceChainController | None = None) -> None:
        self.controller = controller or VoiceChainController()
        self.root = tk.Tk()
        self.root.title("Wanwan Pet")
        self.root.geometry(f"{self.WINDOW_SIZE}x{self.WINDOW_SIZE}+80+80")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.BACKGROUND_KEY)

        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._selected_audio_path = ""
        self._is_running = False
        self._result_queue: queue.Queue[dict[str, object]] = queue.Queue()
        self._transparency_enabled = self._apply_transparency()

        self.canvas = tk.Canvas(
            self.root,
            width=self.WINDOW_SIZE,
            height=self.WINDOW_SIZE,
            bg=self.BACKGROUND_KEY if self._transparency_enabled else "#f7f2ff",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._draw_pet()
        self._bind_events()
        self._build_context_menu()
        self._apply_optional_auto_close()
        self.root.after(100, self._poll_result_queue)

    def run(self) -> None:
        self.root.mainloop()

    def _apply_transparency(self) -> bool:
        try:
            self.root.wm_attributes("-transparentcolor", self.BACKGROUND_KEY)
            return True
        except tk.TclError:
            return False

    def _draw_pet(self) -> None:
        self.canvas.create_oval(18, 28, 142, 152, fill="#fff7f0", outline="#3f2d2d", width=3)
        self.canvas.create_polygon(42, 30, 56, 6, 74, 34, fill="#fff7f0", outline="#3f2d2d", width=3)
        self.canvas.create_polygon(118, 30, 104, 6, 86, 34, fill="#fff7f0", outline="#3f2d2d", width=3)
        self.canvas.create_oval(52, 68, 66, 86, fill="#2c2230", outline="")
        self.canvas.create_oval(94, 68, 108, 86, fill="#2c2230", outline="")
        self.canvas.create_oval(58, 74, 62, 78, fill="#ffffff", outline="")
        self.canvas.create_oval(100, 74, 104, 78, fill="#ffffff", outline="")
        self.canvas.create_oval(72, 96, 88, 108, fill="#ffb3c1", outline="#3f2d2d", width=2)
        self.canvas.create_arc(62, 102, 98, 126, start=200, extent=140, style=tk.ARC, outline="#3f2d2d", width=3)
        self.canvas.create_oval(28, 96, 50, 118, fill="#ffd5df", outline="")
        self.canvas.create_oval(110, 96, 132, 118, fill="#ffd5df", outline="")
        self.pet_label_id = self.canvas.create_text(
            80,
            138,
            text="晚晚",
            fill="#6b4e71",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        self.status_label_id = self.canvas.create_text(
            80,
            18,
            text="待命",
            fill="#3f2d2d",
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _bind_events(self) -> None:
        for widget in (self.root, self.canvas):
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_move)
            widget.bind("<Button-3>", self._show_context_menu)
            widget.bind("<Double-Button-1>", self._exit_app)

    def _build_context_menu(self) -> None:
        self.context_menu = tk.Menu(self.root, tearoff=False)
        self.context_menu.add_command(label="选择音频并运行", command=self._choose_audio_and_run)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="退出", command=self._exit_app)

    def _show_context_menu(self, event: tk.Event) -> None:
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y

    def _on_drag_move(self, event: tk.Event) -> None:
        x = self.root.winfo_pointerx() - self._drag_offset_x
        y = self.root.winfo_pointery() - self._drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def _choose_audio_and_run(self) -> None:
        if self._is_running:
            self._set_status("运行中...")
            return

        initial_dir = Path("data") / "temp"
        selected = filedialog.askopenfilename(
            title="选择本地 webm 音频",
            initialdir=str(initial_dir.resolve()) if initial_dir.exists() else str(Path.cwd()),
            filetypes=[("WebM Audio", "*.webm"), ("All Files", "*.*")],
        )
        if not selected:
            self._set_status("已取消")
            return

        self._selected_audio_path = selected
        self._start_voice_chain()

    def _start_voice_chain(self) -> None:
        if not self._selected_audio_path:
            self._set_status("失败")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "语音链路失败",
                    "step=voice_chain\ncode=VOICE_CHAIN_AUDIO_PATH_REQUIRED\nmessage=请先选择一个本地 webm 音频文件。",
                    parent=self.root,
                ),
            )
            return

        self._is_running = True
        self._set_status("运行中...")
        worker = threading.Thread(target=self._run_voice_chain_worker, daemon=True)
        worker.start()

    def _run_voice_chain_worker(self) -> None:
        result = self.controller.run(audio_path=self._selected_audio_path)
        self._result_queue.put(result)

    def _poll_result_queue(self) -> None:
        try:
            while True:
                result = self._result_queue.get_nowait()
                self._handle_result(result)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_result_queue)

    def _handle_result(self, result: dict[str, object]) -> None:
        self._is_running = False
        if result.get("status") == "success":
            self._set_status("完成")
            return

        failed_stage = result.get("final", {}).get("failed_stage", {}) if isinstance(result.get("final"), dict) else {}
        error = failed_stage.get("error", {}) if isinstance(failed_stage, dict) else {}
        step = str(failed_stage.get("step") or "voice_chain")
        code = str(error.get("code") or "VOICE_CHAIN_UNKNOWN_ERROR")
        message = str(error.get("message") or "未知错误")
        self._set_status("失败")
        self.root.after(
            0,
            lambda: messagebox.showerror(
                "语音链路失败",
                f"step={step}\ncode={code}\nmessage={message}",
                parent=self.root,
            ),
        )

    def _set_status(self, text: str) -> None:
        self.canvas.itemconfigure(self.status_label_id, text=text)

    def _exit_app(self, _event: tk.Event | None = None) -> None:
        self.root.destroy()

    def _apply_optional_auto_close(self) -> None:
        auto_close_ms = os.getenv("WANWAN_DESKTOP_PET_AUTOCLOSE_MS", "").strip()
        if not auto_close_ms:
            return
        try:
            delay = int(auto_close_ms)
        except ValueError:
            return
        if delay > 0:
            self.root.after(delay, self.root.destroy)


def launch_pet_window() -> None:
    """Launch the minimal desktop pet shell."""
    PetWindow().run()

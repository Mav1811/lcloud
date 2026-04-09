"""
Lcloud PC App — Main Window
CustomTkinter UI: backup status, folder picker, progress, history, and settings.
"""
import logging
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from config import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
ACCENT_COLOR = "#4f46e5"
ACCENT_HOVER = "#4338ca"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#94a3b8"
SUCCESS_COLOR = "#22c55e"
WARNING_COLOR = "#f59e0b"
ERROR_COLOR = "#ef4444"


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class _SettingsDialog(ctk.CTkToplevel):
    """Modal dialog for app settings (port number)."""

    def __init__(
        self,
        parent: ctk.CTk,
        current_port: int,
        on_save: Callable[[int], None],
    ) -> None:
        super().__init__(parent)
        self.title("Settings")
        self.geometry("400x230")
        self.resizable(False, False)
        self.configure(fg_color=BG_COLOR)
        self._on_save = on_save

        self.transient(parent)
        self.grab_set()
        self.lift()
        self.focus_force()

        frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        frame.pack(padx=20, pady=20, fill="both", expand=True)
        frame.grid_columnconfigure(1, weight=1)

        # Port row
        ctk.CTkLabel(
            frame, text="Server Port",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        self._port_entry = ctk.CTkEntry(
            frame, width=100, font=ctk.CTkFont(size=13),
        )
        self._port_entry.insert(0, str(current_port))
        self._port_entry.grid(row=0, column=1, padx=(8, 20), pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            frame,
            text="Port the PC listens on for phone connections (1024\u201365535).\nRestart Lcloud to apply a port change.",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="w")

        self._error_label = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=ERROR_COLOR,
        )
        self._error_label.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 4), sticky="w")

        ctk.CTkButton(
            frame, text="Save & Close",
            width=130, height=34,
            fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=13),
            command=self._save,
        ).grid(row=3, column=1, padx=20, pady=(4, 20), sticky="e")

    def _save(self) -> None:
        try:
            port = int(self._port_entry.get().strip())
        except ValueError:
            self._error_label.configure(text="Enter a valid port number.")
            return
        if not (1024 <= port <= 65535):
            self._error_label.configure(text="Port must be between 1024 and 65535.")
            return
        self._on_save(port)
        self.destroy()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class LcloudWindow(ctk.CTk):
    """
    Main application window.

    All public methods that update the UI are thread-safe — they schedule
    updates via after(0, ...) so they run on the Tk main thread.
    """

    def __init__(
        self,
        on_folder_change: Callable[[Path], None] | None = None,
        on_backup_now: Callable[[], None] | None = None,
        on_settings_change: Callable[[int], None] | None = None,
        current_port: int = 52000,
    ) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self._on_folder_change = on_folder_change or (lambda _: None)
        self._on_backup_now = on_backup_now or (lambda: None)
        self._on_settings_change = on_settings_change or (lambda _: None)
        self._current_port = current_port
        self._backup_folder: Path | None = None
        self._log_entries: list[str] = []

        self.title(APP_NAME)
        self.geometry("700x640")
        self.minsize(560, 540)
        self.configure(fg_color=BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    # ------------------------------------------------------------------
    # Thread-safe update methods
    # ------------------------------------------------------------------

    def update_status(self, message: str, color: str = TEXT_PRIMARY) -> None:
        self.after(0, lambda: self._status_label.configure(
            text=message, text_color=color
        ))

    def update_phone_status(self, connected: bool, phone_name: str = "") -> None:
        if connected:
            text = f"\u2022 {phone_name} connected"
            color = SUCCESS_COLOR
        else:
            text = "Searching for phone on WiFi\u2026"
            color = TEXT_SECONDARY
        self.after(0, lambda: self._phone_label.configure(text=text, text_color=color))

    def update_progress(
        self,
        filename: str,
        current: int,
        total: int,
        bytes_done: int,
        bytes_total: int,
    ) -> None:
        pct = (current / total) if total > 0 else 0
        size_done_mb = bytes_done / (1024 * 1024)
        size_total_mb = bytes_total / (1024 * 1024)

        def _update() -> None:
            self._progress_frame.grid()
            self._progress_bar.set(pct)
            self._progress_file_label.configure(
                text=f"Transferring: {Path(filename).name}"
            )
            self._progress_count_label.configure(
                text=f"{current} / {total} files  \u00b7  {size_done_mb:.1f} / {size_total_mb:.1f} MB"
            )
            self.update_status("Backup in progress\u2026", WARNING_COLOR)

        self.after(0, _update)

    def complete_progress(
        self, files_saved: int, bytes_saved: int, errors: list[str]
    ) -> None:
        size_mb = bytes_saved / (1024 * 1024)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"{timestamp}  \u00b7  {files_saved} files  \u00b7  {size_mb:.1f} MB"
        if errors:
            entry += f"  \u00b7  {len(errors)} error(s)"

        def _update() -> None:
            self._progress_frame.grid_remove()
            self._progress_bar.set(0)
            self._add_log_entry(entry)
            self.update_status(
                f"Backup complete \u2014 {files_saved} files saved", SUCCESS_COLOR
            )

        self.after(0, _update)

    def set_backup_folder(self, folder: Path) -> None:
        self._backup_folder = folder
        text = str(folder)
        if len(text) > 52:
            text = f"\u2026{text[-49:]}"
        self.after(0, lambda: self._folder_label.configure(
            text=text, text_color=TEXT_PRIMARY
        ))

    def show_info(self, title: str, message: str) -> None:
        self.after(0, lambda: messagebox.showinfo(title, message, parent=self))

    def show_warning(self, title: str, message: str) -> None:
        self.after(0, lambda: messagebox.showwarning(title, message, parent=self))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # history row expands

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        header.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text=APP_NAME,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        ctk.CTkLabel(
            header, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=1, padx=8, pady=14, sticky="w")

        ctk.CTkButton(
            header, text="\u2699",
            width=36, height=36,
            fg_color="transparent", hover_color="#1e2a45",
            font=ctk.CTkFont(size=20),
            command=self._open_settings,
        ).grid(row=0, column=2, padx=(4, 16), pady=10, sticky="e")

        # --- Status card ---
        status_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        status_frame.grid(row=1, column=0, padx=20, pady=4, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self._phone_label = ctk.CTkLabel(
            status_frame,
            text="Searching for phone on WiFi\u2026",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY,
        )
        self._phone_label.grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        self._status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self._status_label.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="w")

        # --- Folder picker ---
        folder_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        folder_frame.grid(row=2, column=0, padx=20, pady=4, sticky="ew")
        folder_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            folder_frame, text="Backup folder:",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=(20, 8), pady=14)

        self._folder_label = ctk.CTkLabel(
            folder_frame,
            text="Not selected \u2014 click Change",
            font=ctk.CTkFont(size=13),
            text_color=WARNING_COLOR,
        )
        self._folder_label.grid(row=0, column=1, padx=4, pady=14, sticky="w")

        ctk.CTkButton(
            folder_frame, text="Change",
            width=80, height=32,
            fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=12),
            command=self._pick_folder,
        ).grid(row=0, column=2, padx=(4, 20), pady=14)

        # --- Progress (hidden until a backup starts) ---
        self._progress_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        self._progress_frame.grid(row=3, column=0, padx=20, pady=4, sticky="ew")
        self._progress_frame.grid_columnconfigure(0, weight=1)
        self._progress_frame.grid_remove()

        self._progress_file_label = ctk.CTkLabel(
            self._progress_frame, text="",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY,
        )
        self._progress_file_label.grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        self._progress_bar = ctk.CTkProgressBar(
            self._progress_frame,
            height=12,
            progress_color=ACCENT_COLOR,
        )
        self._progress_bar.grid(row=1, column=0, padx=20, pady=4, sticky="ew")
        self._progress_bar.set(0)

        self._progress_count_label = ctk.CTkLabel(
            self._progress_frame, text="",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        )
        self._progress_count_label.grid(row=2, column=0, padx=20, pady=(0, 14), sticky="w")

        # --- Backup history ---
        log_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        log_frame.grid(row=4, column=0, padx=20, pady=4, sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            log_frame, text="Backup History",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=20, pady=(12, 4), sticky="w")

        self._log_box = ctk.CTkTextbox(
            log_frame,
            fg_color=BG_COLOR,
            text_color=TEXT_SECONDARY,
            font=ctk.CTkFont(size=12),
            state="disabled",
        )
        self._log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        # --- Backup Now button ---
        self._backup_btn = ctk.CTkButton(
            self,
            text="Backup Now",
            height=48,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._backup_now,
        )
        self._backup_btn.grid(row=5, column=0, padx=20, pady=(8, 20), sticky="ew")

    # ------------------------------------------------------------------
    # Callbacks and helpers
    # ------------------------------------------------------------------

    def _pick_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Backup Folder")
        if folder:
            path = Path(folder)
            self.set_backup_folder(path)
            self._on_folder_change(path)

    def _backup_now(self) -> None:
        self._on_backup_now()

    def _open_settings(self) -> None:
        def _on_save(port: int) -> None:
            self._current_port = port
            self._on_settings_change(port)

        _SettingsDialog(self, self._current_port, _on_save)

    def _on_close(self) -> None:
        """Minimize to tray instead of quitting."""
        self.withdraw()

    def show(self) -> None:
        """Bring window to front (called from tray)."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _add_log_entry(self, text: str) -> None:
        self._log_entries.append(text)
        if len(self._log_entries) > 50:
            self._log_entries.pop(0)
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        for entry in reversed(self._log_entries):
            self._log_box.insert("end", entry + "\n")
        self._log_box.configure(state="disabled")

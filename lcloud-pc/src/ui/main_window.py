"""
Lcloud PC App — Main Window
CustomTkinter UI showing backup status, controls, and history.
"""
import logging
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from config import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)

# Color palette
BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
ACCENT_COLOR = "#4f46e5"
ACCENT_HOVER = "#4338ca"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#94a3b8"
SUCCESS_COLOR = "#22c55e"
WARNING_COLOR = "#f59e0b"
ERROR_COLOR = "#ef4444"


class LcloudWindow(ctk.CTk):
    """
    Main application window.

    Call `update_status()`, `update_progress()`, `update_phone_status()`
    from any thread — they schedule UI updates safely via `after()`.
    """

    def __init__(
        self,
        on_folder_change: Callable[[Path], None] | None = None,
        on_backup_now: Callable[[], None] | None = None,
    ) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self._on_folder_change = on_folder_change or (lambda _: None)
        self._on_backup_now = on_backup_now or (lambda: None)
        self._backup_folder: Path | None = None
        self._log_entries: list[str] = []

        self.title(APP_NAME)
        self.geometry("680x620")
        self.minsize(560, 520)
        self.configure(fg_color=BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    # ------------------------------------------------------------------
    # Thread-safe update methods (called from backup engine / discovery)
    # ------------------------------------------------------------------

    def update_status(self, message: str, color: str = TEXT_PRIMARY) -> None:
        """Update the main status text."""
        self.after(0, lambda: self._status_label.configure(text=message, text_color=color))

    def update_phone_status(self, connected: bool, phone_name: str = "") -> None:
        """Update the phone connection badge."""
        if connected:
            text = f"Phone connected: {phone_name}"
            color = SUCCESS_COLOR
        else:
            text = "Searching for phone on WiFi..."
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
        """Show transfer progress."""
        pct = (current / total) if total > 0 else 0

        def _update():
            self._progress_frame.grid()
            self._progress_bar.set(pct)
            self._progress_file_label.configure(text=f"Transferring: {filename}")
            self._progress_count_label.configure(text=f"{current} / {total} files")

        self.after(0, _update)

    def complete_progress(self, files_saved: int, bytes_saved: int, errors: list[str]) -> None:
        """Hide progress bar and add entry to history."""
        size_mb = bytes_saved / (1024 * 1024)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"{timestamp}  ·  {files_saved} files  ·  {size_mb:.1f} MB"
        if errors:
            entry += f"  ·  {len(errors)} error(s)"

        def _update():
            self._progress_frame.grid_remove()
            self._progress_bar.set(0)
            self._add_log_entry(entry)
            self.update_status(f"Backup complete — {files_saved} files saved", SUCCESS_COLOR)

        self.after(0, _update)

    def set_backup_folder(self, folder: Path) -> None:
        """Display the currently selected backup folder."""
        self._backup_folder = folder
        short = str(folder) if len(str(folder)) <= 50 else f"...{str(folder)[-47:]}"
        self.after(0, lambda: self._folder_label.configure(text=short, text_color=TEXT_PRIMARY))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

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
        ).grid(row=0, column=1, padx=10, pady=14, sticky="w")

        # --- Status card ---
        status_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        status_frame.grid(row=1, column=0, padx=20, pady=4, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self._phone_label = ctk.CTkLabel(
            status_frame,
            text="Searching for phone on WiFi...",
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
            text="Not selected — click Change",
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

        # --- Progress (hidden by default) ---
        self._progress_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        self._progress_frame.grid(row=3, column=0, padx=20, pady=4, sticky="ew")
        self._progress_frame.grid_columnconfigure(0, weight=1)
        self._progress_frame.grid_remove()  # hidden until backup starts

        self._progress_file_label = ctk.CTkLabel(
            self._progress_frame, text="",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY,
        )
        self._progress_file_label.grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        self._progress_bar = ctk.CTkProgressBar(
            self._progress_frame,
            width=400, height=12,
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

        # --- Log / history ---
        log_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        log_frame.grid(row=4, column=0, padx=20, pady=4, sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

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
    # Callbacks
    # ------------------------------------------------------------------

    def _pick_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Backup Folder")
        if folder:
            path = Path(folder)
            self.set_backup_folder(path)
            self._on_folder_change(path)

    def _backup_now(self) -> None:
        self._on_backup_now()

    def _on_close(self) -> None:
        """Hide window instead of quitting (tray keeps app running)."""
        self.withdraw()

    def show(self) -> None:
        """Bring the window to front."""
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

"""Billing‑Assistant GUI – tabbed layout
Fixed so that the *Program* tab is a proper `QStackedWidget` inside the
`QTabWidget`, and `main()` just builds the tabs once.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------
# Helper screens for the Program flow
# ---------------------------------------------------------------------

def create_welcome_screen(stack: QStackedWidget, state: Dict) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)

    label = QLabel("Welcome to the Billing Assistant! Index 0, Step 1")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    file_label = QLabel("No files selected.")
    layout.addWidget(file_label)

    select_files_btn = QPushButton("Select CSV Files")
    select_folder_btn = QPushButton("Select Folder")

    def load_paths(paths: List[str]):
        state["csv_paths"] = paths
        dfs, errors = [], []
        for p in paths:
            try:
                dfs.append(pd.read_csv(p))
            except Exception as exc:
                errors.append(f"{p}: {exc}")
        state["dataframes"] = dfs
        state["df"] = pd.concat(dfs, ignore_index=True) if dfs else None
        msg = f"Loaded {len(dfs)} files"
        if errors:
            msg += f" ( {len(errors)} failed )"
        file_label.setText(msg)

    def select_files():
        paths, _ = QFileDialog.getOpenFileNames(
            screen, "Select CSV Files", "", "CSV Files (*.csv);;All Files (*)"
        )
        if paths:
            load_paths(paths)

    def select_folder():
        folder = QFileDialog.getExistingDirectory(screen, "Select Folder Containing CSV Files", "")
        if folder:
            paths = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(".csv")
            ]
            if paths:
                load_paths(paths)

    select_files_btn.clicked.connect(select_files)
    select_folder_btn.clicked.connect(select_folder)

    layout.addWidget(select_files_btn)
    layout.addWidget(select_folder_btn)

    next_btn = QPushButton("Next")
    next_btn.clicked.connect(lambda: stack.setCurrentIndex(1))
    layout.addWidget(next_btn)

    exit_btn = QPushButton("Exit Program")
    exit_btn.clicked.connect(QApplication.quit)
    layout.addWidget(exit_btn)

    return screen


def create_session_creation_screen(stack: QStackedWidget) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)
    lbl = QLabel("Session Creation (Index 1, Step 2)")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)

    next_btn = QPushButton("Next")
    next_btn.setFixedSize(400, 125)
    next_btn.clicked.connect(lambda: stack.setCurrentIndex(2))
    layout.addWidget(next_btn)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(0))
    layout.addWidget(back_btn)
    return screen


def create_assign_status_screen(stack: QStackedWidget) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)
    lbl = QLabel("Status Assignment (Index 2, Step 3)")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)

    next_btn = QPushButton("Next")  # placeholder
    layout.addWidget(next_btn)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(1))
    layout.addWidget(back_btn)
    return screen


# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------

def create_program_flow_tab(state: Dict) -> QStackedWidget:
    """Returns a QStackedWidget containing the three program steps."""
    stack = QStackedWidget()
    stack.addWidget(create_welcome_screen(stack, state))
    stack.addWidget(create_session_creation_screen(stack))
    stack.addWidget(create_assign_status_screen(stack))
    stack.setCurrentIndex(0)
    return stack


def create_flagged_sessions_tab(state: Dict) -> QWidget:
    scr = QWidget()
    lay = QVBoxLayout(scr)
    lbl = QLabel("This tab was intentionally left blank.")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl)
    return scr


def create_session_crud_tab(state: Dict) -> QWidget:
    scr = QWidget()
    lay = QVBoxLayout(scr)
    lbl = QLabel("This tab was *also* intentionally left blank.")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl)
    return scr


# ---------------------------------------------------------------------
# Main window builder
# ---------------------------------------------------------------------

def create_main_window() -> QTabWidget:
    tabs = QTabWidget()
    state: Dict = {}

    tabs.addTab(create_program_flow_tab(state), "Program")
    tabs.addTab(create_flagged_sessions_tab(state), "Flagged")
    tabs.addTab(create_session_crud_tab(state), "Session Admin")
    return tabs


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    window = create_main_window()
    window.setWindowTitle("Billing Assistant")
    window.resize(600, 450)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

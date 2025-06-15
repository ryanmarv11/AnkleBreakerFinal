"""Billing‑Assistant GUI – tabbed layout
Fixed so that the *Program* tab is a proper `QStackedWidget` inside the
`QTabWidget`, and `main()` just builds the tabs once.
"""
from __future__ import annotations

import os
import sys
import json
from typing import Dict, List

import pandas as pd

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QDateEdit,
    QComboBox,
    QLineEdit,
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

    # --- Custom default status logic ---
    def determine_default_status(notes: str) -> str:
        n = str(notes).lower()
        if "comped" in n:
            return "comped"
        elif "refund" in n:
            return "refund"
        elif "manually confirmed by" in n:
            return "manual"
        elif "not over capacity: register" in n:
            return "regular"
        else:
            return "other"

    def load_paths(paths: List[str]):
        state["csv_paths"] = paths
        dfs, errors = [], []
        for p in paths:
            try:
                df = pd.read_csv(p, skiprows=1, header=None)  # Skip first row
                df.columns = ["Name", "Email", "Phone Number", "Status", "Registration Time", "Notes"]

                # Add default_status based on notes
                df["default_status"] = df["Notes"].apply(determine_default_status)
                dfs.append(df)

            except Exception as exc:
                errors.append(f"{p}: {exc}")

        state["dataframes"] = dfs
        state["df"] = pd.concat(dfs, ignore_index=True) if dfs else None

        print(state["df"].columns)
        print(state["df"])

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
    main_layout = QHBoxLayout(screen)
    clubs = ["None", "Zorano", "notZorano"]

    # LEFT SIDE
    left_layout = QVBoxLayout()
    lbl = QLabel("Session Creation (Index 1, Step 2)")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    left_layout.addWidget(lbl)

    date_wid = QDateEdit()
    date_wid.setCalendarPopup(True)
    date_wid.setDisplayFormat(" ")  # Hide default format
    date_wid.clear()  # Clears visible value
    left_layout.addWidget(date_wid)

    date_label = QLabel("No date selected yet!")
    left_layout.addWidget(date_label)

    # Status labels
    status_date = QLabel("Date selected: ❌")
    status_club = QLabel("Club selected: ❌")
    status_ready = QLabel("Ready to create session: ❌")
    left_layout.addWidget(status_date)
    left_layout.addWidget(status_club)
    left_layout.addWidget(status_ready)

    # Dropdown
    club_selector = QComboBox()
    club_selector.addItems(clubs)
    club_selector.setCurrentIndex(0)
    left_layout.addWidget(club_selector)

    # Create Session button
    create_btn = QPushButton("Create Session")
    create_btn.setEnabled(False)
    left_layout.addWidget(create_btn)

    # Next/Back
    next_btn = QPushButton("Next")
    next_btn.clicked.connect(lambda: stack.setCurrentIndex(2))
    left_layout.addWidget(next_btn)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(0))
    left_layout.addWidget(back_btn)

    # Track date selection state
    date_selected = False

    # -- Refresh logic --
    def update_status():
        # Use outer `date_selected` flag
        club_selected = club_selector.currentText() != "None"

        status_date.setText(f"Date selected: {'✅' if date_selected else '❌'}")
        status_club.setText(f"Club selected: {'✅' if club_selected else '❌'}")
        ready = date_selected and club_selected
        status_ready.setText(f"Ready to create session: {'✅' if ready else '❌'}")
        create_btn.setEnabled(ready)

    def on_date_changed(date):
        nonlocal date_selected
        if not date_selected:
            # Only do this once when user selects the date
            date_wid.setDisplayFormat("MMMM d, yyyy")
        date_selected = True
        date_label.setText("Selected date: " + date.toString("MMMM d, yyyy"))
        update_status()

    date_wid.dateChanged.connect(on_date_changed)
    club_selector.currentTextChanged.connect(lambda _: update_status())
    update_status()

    def create_session():
        club_name = club_selector.currentText()
        date_str = date_wid.date().toString("yyyy-MM-dd")
        session_name = f"Session-{club_name}-{date_str}"
        base_dir = os.getcwd()
        sessions_path = os.path.join(base_dir, "sessions")
        session_path = os.path.join(sessions_path, session_name)

        os.makedirs(os.path.join(session_path, "csv"), exist_ok=True)
        os.makedirs(os.path.join(session_path, "metadata"), exist_ok=True)

        metadata = {
            "club": club_name,
            "date": date_str,
            "session_name": session_name,
        }

        metadata_path = os.path.join(session_path, "metadata", "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)

        status_ready.setText("Session created successfully ✅")

    create_btn.clicked.connect(create_session)

    # RIGHT SIDE - Club Management
    right_layout = QVBoxLayout()

    club_input = QLineEdit()
    club_input.setPlaceholderText("Enter club name")
    right_layout.addWidget(club_input)

    def refresh_dropdown():
        club_selector.clear()
        club_selector.addItems(clubs)
        update_status()

    def add_club():
        new_club = club_input.text().strip()
        if new_club and new_club not in clubs:
            clubs.append(new_club)
            refresh_dropdown()
            club_input.clear()

    def remove_club():
        club_to_remove = club_input.text().strip()
        if club_to_remove in clubs:
            clubs.remove(club_to_remove)
            refresh_dropdown()
            club_input.clear()

    add_button = QPushButton("Add Club")
    add_button.clicked.connect(add_club)
    right_layout.addWidget(add_button)

    remove_button = QPushButton("Remove Club")
    remove_button.clicked.connect(remove_club)
    right_layout.addWidget(remove_button)

    main_layout.addLayout(left_layout, stretch=2)
    main_layout.addLayout(right_layout, stretch=1)

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

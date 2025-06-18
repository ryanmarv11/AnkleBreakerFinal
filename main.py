from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

from collections import defaultdict 

import pandas as pd

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QStackedWidget,
    QTabWidget,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QButtonGroup,
    QDateEdit,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QFormLayout,
    QMessageBox,
    QScrollArea,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox
)
from PyQt6.QtWidgets import QMessageBox

from pathlib import Path

BASE_DIR      = Path.home() / "AnkleBreakerData"
BASE_DIR.mkdir(parents=True, exist_ok=True)

ROOT_METADATA_PATH = BASE_DIR / "metadata.json"
SESSIONS_DIR       = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)               # ensure it exists

# Ensure metadata.json exists in the current directory

DEFAULT_CLUBS = ["Zorano"]

def load_global_metadata() -> dict:
    if not os.path.exists(ROOT_METADATA_PATH):
        with open(ROOT_METADATA_PATH, "w") as f:
            json.dump({"clubs": DEFAULT_CLUBS}, f, indent=4)
    with open(ROOT_METADATA_PATH) as f:
        return json.load(f)

def save_global_metadata(data: dict):
    with open(ROOT_METADATA_PATH, "w") as f:
        json.dump(data, f, indent=4)


# ---------------------------------------------------------------------
# Screens for Program Flow Tab
# ---------------------------------------------------------------------

#This is the first screen that the user sees
def create_welcome_screen(stack: QStackedWidget, state: Dict) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)

    label = QLabel("Welcome to the AnkleBreaker")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    file_label = QLabel("No files selected.")
    layout.addWidget(file_label)

    select_files_btn = QPushButton("Select CSV Files")
    select_folder_btn = QPushButton("Select Folder")
    load_session_btn = QPushButton("Select Previous Session")  # ✅ NEW button

    layout.addWidget(select_files_btn)
    layout.addWidget(select_folder_btn)
    layout.addWidget(load_session_btn)  # ✅ Add after the others

    next_btn = QPushButton("Next")
    next_btn.setEnabled(False)  # Start disabled
    layout.addWidget(next_btn)

    exit_btn = QPushButton("Exit Program")
    exit_btn.clicked.connect(QApplication.quit)
    layout.addWidget(exit_btn)

    next_btn.clicked.connect(lambda: stack.setCurrentIndex(1))

    def determine_default_status(notes: str) -> str:
        n = str(notes).lower()
        if "comped" in n:
            return "comped"
        elif "no capacity, and room on the waiting list : register" in n:
            return "waitlist"
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
                df = pd.read_csv(p, skiprows=1, header=None)
                df.columns = ["Name", "Email", "Phone Number", "Status", "Registration Time", "Notes"]
                df["default_status"] = df["Notes"].apply(determine_default_status)
                dfs.append(df)
            except Exception as exc:
                errors.append(f"{p}: {exc}")

        state["dataframes"] = dfs
        state["df"] = pd.concat(dfs, ignore_index=True) if dfs else None

        msg = f"Loaded {len(dfs)} files"
        if errors:
            msg += f" ( {len(errors)} failed )"
        file_label.setText(msg)
        next_btn.setEnabled(len(dfs) > 0)

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

    # ✅ NEW: Load a previous session from folder and jump to assign screen
    def load_previous_session():
        session_dir = QFileDialog.getExistingDirectory(screen, "Select a Previous Session Folder", str(SESSIONS_DIR))
        if not session_dir:
            return

        metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
        csv_dir = os.path.join(session_dir, "csv")

        if not os.path.exists(metadata_path) or not os.path.isdir(csv_dir):
            QMessageBox.warning(screen, "Invalid Session", "Selected folder does not appear to be a valid session.")
            return

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # ✅ Extract and store fees
            fees = metadata.get("fees", {})
            state["fee_schedule"] = {fname: int(val) for fname, val in fees.items() if str(val).isdigit()}

            state["current_session"] = session_dir
            state["csv_paths"] = []
            state["dataframes"] = []
            state["status_counts"] = {}

            filenames = sorted(f for f in os.listdir(csv_dir) if f.endswith(".csv"))
            for fname in filenames:
                path = os.path.join(csv_dir, fname)
                df = pd.read_csv(path)
                if "default_status" in df.columns:
                    if "current_status" not in df.columns:
                        df["current_status"] = df["default_status"]
                    state["dataframes"].append(df)
                    state["csv_paths"].append(path)

            if "_refresh_crud_banner" in state:
                state["_refresh_crud_banner"]()

            new_assign_screen = create_assign_status_screen(stack, state)
            stack.removeWidget(stack.widget(2))
            stack.insertWidget(2, new_assign_screen)
            stack.setCurrentIndex(2)

        except Exception as e:
            QMessageBox.critical(screen, "Load Failed", f"Could not load session:\n{e}")

    select_files_btn.clicked.connect(select_files)
    select_folder_btn.clicked.connect(select_folder)
    load_session_btn.clicked.connect(load_previous_session)  # ✅ Connect new button

    return screen

#This is the second screen that the user sees and after clicking next is the point of no return
def create_session_creation_screen(stack: QStackedWidget, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)
    clubs = ["None"] + state["global_metadata"].get("clubs", [])

    # LEFT SIDE
    left_layout = QVBoxLayout()
    lbl = QLabel("Session Creation")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    left_layout.addWidget(lbl)

    # --- Date widget -------------------------------------------------
    date_wid = QDateEdit()
    date_wid.setCalendarPopup(True)
    date_wid.setDisplayFormat("MMMM d, yyyy")          # show pretty date format
    date_wid.setDate(QDate.currentDate())              # default = today
    left_layout.addWidget(date_wid)

    # Selected-date label
    date_label = QLabel(f"Selected date: {date_wid.date().toString('MMMM d, yyyy')}")
    left_layout.addWidget(date_label)

    # Status labels
    status_date = QLabel("Date selected: ✅")           # already true
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

    # Track date selection state – starts True because we pre-picked today
    date_selected = True

    # -- Refresh logic ------------------------------------------------
    def update_status():
        club_selected = club_selector.currentText() != "None"
        status_date.setText(f"Date selected: {'✅' if date_selected else '❌'}")
        status_club.setText(f"Club selected: {'✅' if club_selected else '❌'}")
        ready = date_selected and club_selected
        status_ready.setText(f"Ready to create session: {'✅' if ready else '❌'}")
        create_btn.setEnabled(ready)

    # Fires on date *change*
    def on_date_changed(new_date):
        nonlocal date_selected
        date_selected = True
        date_label.setText("Selected date: " + new_date.toString("MMMM d, yyyy"))
        update_status()

    # Fires even when the user clicks the SAME date again
    date_wid.calendarWidget().clicked.connect(on_date_changed)
    date_wid.dateChanged.connect(on_date_changed)

    club_selector.currentTextChanged.connect(lambda _: update_status())
    update_status()

    # --------------------- Core “create session” logic ----------------
    def create_session():
        club_name = club_selector.currentText()
        date_str = date_wid.date().toString("yyyy-MM-dd")
        base_session_name = f"Session-{club_name}-{date_str}"

        flagged = False
        flagged_files = []

        sessions_path = SESSIONS_DIR
        os.makedirs(sessions_path, exist_ok=True)

        if "csv_paths" not in state or "dataframes" not in state:
            status_ready.setText("Error: No data loaded in state.")
            return

        # Step 1: Check for flags
        file_output = []
        for path, df in zip(state["csv_paths"], state["dataframes"]):
            original_filename = os.path.basename(path)
            filename_out = original_filename
            if "default_status" in df.columns and (df["default_status"] == "other").any():
                flagged = True
                filename_out = original_filename.replace(".csv", "-flag.csv")
                flagged_files.append(filename_out)
            file_output.append((df, filename_out))

        # Step 2: Determine unique session name
        session_folder_base = f"{base_session_name}-flag" if flagged else base_session_name
        session_name = session_folder_base
        suffix = 2
        while os.path.exists(os.path.join(sessions_path, session_name)):
            session_name = f"{session_folder_base}-v{suffix}"
            suffix += 1

        session_path = os.path.join(sessions_path, session_name)
        os.makedirs(os.path.join(session_path, "csv"), exist_ok=True)
        os.makedirs(os.path.join(session_path, "metadata"), exist_ok=True)

        # Step 3: Write files with duplicate protection
        written_filenames = set()
        final_csv_paths = []

        for df, desired_name in file_output:
            name_base = desired_name.rsplit(".csv", 1)[0]
            actual_filename = desired_name
            suffix = 2
            while (actual_filename in written_filenames or
                   os.path.exists(os.path.join(session_path, "csv", actual_filename))):
                actual_filename = f"{name_base}-v{suffix}.csv"
                suffix += 1

            written_filenames.add(actual_filename)
            csv_full_path = os.path.join(session_path, "csv", actual_filename)
            df.to_csv(csv_full_path, index=False)
            final_csv_paths.append(csv_full_path)

        # Step 4: Store updated paths and reload fresh DataFrames
        state["csv_paths"] = final_csv_paths
        state["dataframes"] = [pd.read_csv(p) for p in final_csv_paths]
        state["current_session"] = session_path

        if "_refresh_crud_banner" in state:
            state["_refresh_crud_banner"]()      # tell the admin tab the good news


        # Step 5: Write metadata
        metadata = {
            "club": club_name,
            "date": date_str,
            "session_name": session_name,
            "paid": False,
            "flagged": flagged,
            "flagged_files": flagged_files,
        }

        metadata_path = os.path.join(session_path, "metadata", "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)

        status_ready.setText(f"Session created: {session_name}")

        # Step 6: 🔄 Rebuild assign status screen so it doesn't use stale data
        new_assign = create_assign_status_screen(stack, state)
        stack.removeWidget(stack.widget(2))
        stack.insertWidget(2, new_assign)
        stack.setCurrentIndex(2)

    create_btn.clicked.connect(create_session)

    # RIGHT SIDE – Club Management ------------------------------------

    right_group = QGroupBox("Club Management")
    right_layout = QFormLayout(right_group)

    club_input = QLineEdit()
    club_input.setPlaceholderText("Enter club name")
    right_layout.addRow(QLabel("Club Name:"), club_input)

    add_button = QPushButton("Add Club")
    remove_button = QPushButton("Remove Club")
    btn_row = QHBoxLayout()
    btn_row.addWidget(add_button)
    btn_row.addWidget(remove_button)
    right_layout.addRow(QLabel("Actions:"), btn_row)

    def refresh_dropdown():
        club_selector.clear()
        club_selector.addItems(clubs)
        update_status()

    def add_club():
        new_club = club_input.text().strip()
        if not new_club or new_club in clubs:
            return
        clubs.append(new_club)
        state["global_metadata"]["clubs"].append(new_club)
        save_global_metadata(state["global_metadata"])
        refresh_dropdown()
        club_input.clear()

    def remove_club():
        club_to_remove = club_input.text().strip()
        if club_to_remove in clubs and club_to_remove != "Zorano":
            clubs.remove(club_to_remove)
            state["global_metadata"]["clubs"].remove(club_to_remove)
            save_global_metadata(state["global_metadata"])
            refresh_dropdown()
            club_input.clear()

    add_button.clicked.connect(add_club)
    remove_button.clicked.connect(remove_club)


    main_layout.addLayout(left_layout, stretch=2)
    main_layout.addWidget(right_group, stretch=1)

    return screen

#This is the third scrren that the user sees and is the first step after a session is created
#A user cannot backtrack past this screen
def create_assign_status_screen(stack, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)

    # Left layout
    left_layout = QVBoxLayout()
    lbl = QLabel("Status Assignment")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    left_layout.addWidget(lbl)

    file_dropdown = QComboBox()
    left_layout.addWidget(file_dropdown)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll_content = QWidget()
    scroll_layout = QVBoxLayout(scroll_content)
    scroll.setWidget(scroll_content)
    left_layout.addWidget(scroll)

    # Right layout (other display)
    right_layout = QVBoxLayout()
    other_display = QTextEdit()
    other_display.setReadOnly(True)
    right_layout.addWidget(QLabel("People with status 'Other' (by file):"))
    right_layout.addWidget(other_display)

    # Get current session folder from state
    current_session = state.get("current_session")
    dataframes = []
    session_csvs = []

    if current_session and os.path.exists(current_session):
        csv_dir = os.path.join(current_session, "csv")
    else:
        # Fallback to latest session if none recorded
        folders = [
            os.path.join(SESSIONS_DIR, f)
            for f in os.listdir(SESSIONS_DIR)
            if os.path.isdir(os.path.join(SESSIONS_DIR, f))
        ]
        latest_session = max(folders, key=os.path.getctime, default=None)
        csv_dir = os.path.join(latest_session, "csv") if latest_session else None

    if csv_dir and os.path.exists(csv_dir):
        for fname in sorted(os.listdir(csv_dir)):
            if fname.endswith(".csv"):
                path = os.path.join(csv_dir, fname)
                try:
                    df = pd.read_csv(path)
                    if "default_status" in df.columns:
                        if "current_status" not in df.columns:
                            df["current_status"] = df["default_status"]
                        dataframes.append(df)
                        session_csvs.append(fname)
                except Exception as e:
                    print(f"Error reading {path}: {e}")

    state["dataframes"] = dataframes
    state["csv_paths"] = [os.path.join(csv_dir, f) for f in session_csvs]
    state["status_counts"] = {}

    def update_other_display():
        content = ""
        for fname, df in zip(session_csvs, dataframes):
            others = df[df["current_status"] == "other"]["Name"].tolist()
            if others:
                content += f"{fname}:\n"
                for name in others:
                    content += f"  {name}\n"
        other_display.setText(content.strip())

    def update_status_counts():
        counts_per_file = {}
        for fname, df in zip(session_csvs, dataframes):
            counts = df["current_status"].value_counts().to_dict()
            counts_per_file[fname] = counts
        state["status_counts"] = counts_per_file

    def update_person_buttons(df_index):
        while scroll_layout.count():
            child = scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        df = dataframes[df_index]

        for idx, row in df.iterrows():
            person_box = QVBoxLayout()
            person_label = QLabel(f"{row['Name']} — Default: {row['default_status']}")
            person_box.addWidget(person_label)

            button_row = QHBoxLayout()
            statuses = ["regular", "manual", "comped", "refund", "waitlist", "other"]

            button_group = QButtonGroup(screen)
            button_group.setExclusive(True)

            for status in statuses:
                btn = QPushButton(status.capitalize())
                btn.setCheckable(True)
                if row["current_status"] == status:
                    btn.setChecked(True)

                def make_click_handler(status=status, row_idx=idx, df=df):
                    def handler():
                        df.at[row_idx, "current_status"] = status
                        update_other_display()
                        update_status_counts()
                    return handler

                btn.clicked.connect(make_click_handler())
                button_group.addButton(btn)
                button_row.addWidget(btn)

            person_box.addLayout(button_row)
            wrapper = QFrame()
            wrapper.setLayout(person_box)
            wrapper.setFrameShape(QFrame.Shape.Box)
            scroll_layout.addWidget(wrapper)

        update_status_counts()

    update_other_display()
    file_dropdown.addItems(session_csvs)
    file_dropdown.currentIndexChanged.connect(update_person_buttons)

    if dataframes:
        update_person_buttons(0)

    def go_to_fee_schedule():
        fee_screen = create_fee_schedule_screen(stack, state)
        stack.removeWidget(stack.widget(3))
        stack.insertWidget(3, fee_screen)
        stack.setCurrentIndex(3)

    next_btn = QPushButton("Next")
    next_btn.clicked.connect(go_to_fee_schedule)
    left_layout.addWidget(next_btn)

    main_layout.addLayout(left_layout, stretch=3)
    main_layout.addLayout(right_layout, stretch=1)

    return screen


#This is the fourth screen that the user sees
def create_fee_schedule_screen(stack, state) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)

    layout.addWidget(QLabel("Fee Schedule"))

    fee_inputs: Dict[str, QLineEdit] = {}
    state["fee_schedule"] = {}

    validator = QIntValidator()
    validator.setBottom(1)

    csv_paths = state.get("csv_paths", [])
    file_basenames = [os.path.basename(p) for p in csv_paths]

    # Load any previously saved fees
    saved_prices = {}
    session_dir = state.get("current_session")
    if session_dir:
        metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    meta = json.load(f)
                    saved_prices = meta.get("fees", {})
            except:
                pass

    file_form = QFormLayout()
    if not file_basenames:
        layout.addWidget(QLabel("⚠️ No CSV files found for this session."))
    else:
        for fname in file_basenames:
            inp = QLineEdit()
            inp.setValidator(validator)
            inp.setPlaceholderText("Enter cost")
            if fname in saved_prices:
                inp.setText(str(saved_prices[fname]))
            file_form.addRow(QLabel(fname), inp)
            fee_inputs[fname] = inp

    layout.addLayout(file_form)

    layout.addWidget(QLabel("Bulk Assign to All:"))
    bulk_input = QLineEdit()
    bulk_input.setValidator(validator)
    bulk_input.setPlaceholderText("Enter fee to apply to all")
    layout.addWidget(bulk_input)

    def assign_all():
        val = bulk_input.text()
        if val:
            for field in fee_inputs.values():
                field.setText(val)

    def reset_all():
        bulk_input.clear()
        for field in fee_inputs.values():
            field.clear()
        state["fee_schedule"].clear()

    assign_all_btn = QPushButton("Assign All")
    assign_all_btn.clicked.connect(assign_all)
    layout.addWidget(assign_all_btn)

    reset_all_btn = QPushButton("Reset All")
    reset_all_btn.clicked.connect(reset_all)
    layout.addWidget(reset_all_btn)

    # ✅ Save Fee Schedule button
    save_btn = QPushButton("Save Fee Schedule")
    def save_fee_schedule():
        prices = {}
        for fname in file_basenames:
            text = fee_inputs[fname].text()
            if text.isdigit():
                prices[fname] = int(text)

        if not session_dir:
            QMessageBox.warning(screen, "No Session", "No active session to save fees to.")
            return

        metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
        if not os.path.exists(metadata_path):
            QMessageBox.warning(screen, "Missing Metadata", "Metadata file not found in current session.")
            return

        try:
            with open(metadata_path, "r") as f:
                meta = json.load(f)
            meta["fees"] = prices
            with open(metadata_path, "w") as f:
                json.dump(meta, f, indent=4)
            QMessageBox.information(screen, "Saved", "Fee schedule saved to metadata.")
        except Exception as e:
            QMessageBox.critical(screen, "Error", f"Failed to save fees:\n{e}")

    save_btn.clicked.connect(save_fee_schedule)
    layout.addWidget(save_btn)

    # Navigation
    nav_row = QHBoxLayout()

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(2))
    nav_row.addWidget(back_btn)

    def save_and_continue():
        for fname in file_basenames:
            text = fee_inputs[fname].text()
            if text.isdigit():
                state["fee_schedule"][fname] = int(text)

        summary_screen = create_payment_summary_screen(stack, state)
        stack.removeWidget(stack.widget(4))
        stack.insertWidget(4, summary_screen)
        stack.setCurrentIndex(4)

    next_btn = QPushButton("Next")
    next_btn.clicked.connect(save_and_continue)
    nav_row.addWidget(next_btn)

    reset_btn = QPushButton("Reset Session")
    def reset_session():
        # Clear state
        keys_to_clear = ["csv_paths", "dataframes", "df", "current_session", "fee_schedule", "status_counts", "_last_selected_file"]
        for key in keys_to_clear:
            state.pop(key, None)

        # Rebuild all major screens (indexes 0–2 at least)
        stack.removeWidget(stack.widget(0))
        stack.removeWidget(stack.widget(1))
        stack.removeWidget(stack.widget(2))

        stack.insertWidget(0, create_welcome_screen(stack, state))
        stack.insertWidget(1, create_session_creation_screen(stack, state))
        stack.insertWidget(2, create_assign_status_screen(stack, state))

        stack.setCurrentIndex(0)

        # Update admin banner if applicable
        if "_refresh_crud_banner" in state:
            state["_refresh_crud_banner"]()

    reset_btn.clicked.connect(reset_session)
    nav_row.addWidget(reset_btn)

    layout.addLayout(nav_row)
    return screen


# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------

def create_program_flow_tab(state: Dict) -> QStackedWidget:
    stack = QStackedWidget()
    state["stack"] = stack

    stack.addWidget(create_welcome_screen(stack, state))             # 0
    stack.addWidget(create_session_creation_screen(stack, state))    # 1
    stack.addWidget(create_assign_status_screen(stack, state))       # 2
    stack.addWidget(QWidget())  # Placeholder for fee screen          # 3
    stack.addWidget(QWidget())  # Placeholder for payment summary     # 4

    return stack


def create_flagged_sessions_tab(state: Dict) -> QWidget:
    scr = QWidget()
    layout = QVBoxLayout(scr)

    header = QLabel("Flagged Sessions Overview")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addWidget(tree)

    def refresh_flagged():
        tree.clear()

        sessions_path = SESSIONS_DIR

        if not os.path.exists(sessions_path):
            return

        for session_name in sorted(os.listdir(sessions_path)):
            session_path = os.path.join(sessions_path, session_name)
            metadata_path = os.path.join(session_path, "metadata", "metadata.json")
            if not os.path.exists(metadata_path):
                continue

            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                if metadata.get("flagged"):
                    parent_item = QTreeWidgetItem([session_name])
                    flagged_files = metadata.get("flagged_files", [])
                    for file_name in flagged_files:
                        QTreeWidgetItem(parent_item, [file_name])
                    tree.addTopLevelItem(parent_item)
            except Exception as e:
                print(f"Error reading {metadata_path}: {e}")

    refresh_btn = QPushButton("Refresh")
    refresh_btn.clicked.connect(refresh_flagged)
    layout.addWidget(refresh_btn)

    refresh_flagged()

    return scr

def create_payment_summary_screen(stack, state) -> QWidget:


    screen = QWidget()
    layout = QVBoxLayout(screen)

    header = QLabel("Payment Summary")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    # ------------------------------
    # Table 1: Status Count Summary
    # ------------------------------
    statuses = ["regular", "manual", "comped", "refund", "waitlist", "other"]
    status_table = QTableWidget()
    layout.addWidget(status_table)

    status_counts = state.get("status_counts", {})
    filenames = list(status_counts.keys())

    status_table.setRowCount(len(filenames) + 1)
    status_table.setColumnCount(len(statuses))
    status_table.setHorizontalHeaderLabels([s.capitalize() for s in statuses])
    status_table.setVerticalHeaderLabels(filenames + ["Total"])

    totals = dict.fromkeys(statuses, 0)

    for row_idx, fname in enumerate(filenames):
        counts = status_counts.get(fname, {})
        for col_idx, status in enumerate(statuses):
            count = int(counts.get(status, 0))
            item = QTableWidgetItem(str(count))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_table.setItem(row_idx, col_idx, item)

            totals[status] += count

    for col_idx, status in enumerate(statuses):
        status_table.setItem(len(filenames), col_idx, QTableWidgetItem(str(totals[status])))

    status_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ------------------------------
    # Table 2: Financial Breakdown
    # ------------------------------
    layout.addWidget(QLabel("Financial Summary"))

    columns = ["Gross", "TrackitHub", "PayPal", "Zorano"]
    financial_table = QTableWidget()
    financial_table.setColumnCount(len(columns))
    financial_table.setRowCount(len(filenames) + 1)
    financial_table.setHorizontalHeaderLabels(columns)
    financial_table.setVerticalHeaderLabels(filenames + ["Total"])
    layout.addWidget(financial_table)

    fee_schedule = state.get("fee_schedule", {})
    totals = dict.fromkeys(columns, 0.0)
    for row_idx, fname in enumerate(filenames):
        price = fee_schedule.get(fname, 0)
        

        counts = status_counts.get(fname, {})

        regular = counts.get("regular", 0)
        manual = counts.get("manual", 0)
        refund = counts.get("refund", 0)

        # Explicit Calculations
        gross = regular * price
        trackithub = (regular + manual) * price * 0.10

        paypal = 0.0
        paypal_count = regular + refund
        for _ in range(paypal_count):
            if price <= 10:
                paypal += price * 0.05 + 0.05
            else:
                paypal += price * 0.0349 + 0.49

        zorano = gross - trackithub - paypal

        row_values = [gross, trackithub, paypal, zorano]
        for col_idx, value in enumerate(row_values):
            item = QTableWidgetItem(f"${value:.2f}")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            financial_table.setItem(row_idx, col_idx, item)

            totals[columns[col_idx]] += value

    for col_idx, col_name in enumerate(columns):
        financial_table.setItem(len(filenames), col_idx, QTableWidgetItem(f"${totals[col_name]:.2f}"))

    financial_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ------------------------------
    # Navigation
    # ------------------------------
    nav_row = QHBoxLayout()
    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(3))
    nav_row.addWidget(back_btn)

    layout.addLayout(nav_row)

    return screen


def create_session_admin_tab(state: Dict) -> QWidget:
    """Session-admin tab: pay/unpay/delete + live ‘current session’ banner, with club → date → session filtering."""
    scr = QWidget()
    layout = QVBoxLayout(scr)

    header = QLabel("Session Admin")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    # -------- banner -------------------------------------------------
    current_session_lbl = QLabel()
    layout.addWidget(current_session_lbl)

    def refresh_current_session_label() -> None:
        path = state.get("current_session")
        current_session_lbl.setText(
            f"Current Session: {os.path.basename(path)}"
            if path else "No session created yet"
        )

    refresh_current_session_label()
    state["_refresh_crud_banner"] = refresh_current_session_label
    # -----------------------------------------------------------------

    # Dropdowns
    club_selector = QComboBox()
    club_selector.addItems(["Select a club..."] + state["global_metadata"].get("clubs", []))
    layout.addWidget(QLabel("Select a club:"))
    layout.addWidget(club_selector)

    date_selector = QComboBox()
    layout.addWidget(QLabel("Select a date:"))
    layout.addWidget(date_selector)

    session_dropdown = QComboBox()
    layout.addWidget(QLabel("Select a session:"))
    layout.addWidget(session_dropdown)

    # Status label
    status_label = QLabel("Select a session to view or update its paid status.")
    layout.addWidget(status_label)

    sessions_path = SESSIONS_DIR

    def meta_path(sess_name: str) -> str:
        return os.path.join(sessions_path, sess_name, "metadata", "metadata.json")

    def update_status_label() -> None:
        sess = session_dropdown.currentText()
        mpath = meta_path(sess)
        if not os.path.exists(mpath):
            status_label.setText("No metadata found for selected session.")
            return
        try:
            with open(mpath) as f:
                paid = json.load(f).get("paid", False)
            status_label.setText(f"Current status: {'✅ Paid' if paid else '❌ Unpaid'}")
        except Exception as exc:
            status_label.setText(f"Error reading metadata: {exc}")

    def load_club_dates() -> Dict[str, List[str]]:
        club_dates = defaultdict(set)
        if not os.path.exists(sessions_path):
            return {}
        for session_name in os.listdir(sessions_path):
            metadata_path = os.path.join(sessions_path, session_name, "metadata", "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path) as f:
                        meta = json.load(f)
                    club = meta.get("club")
                    date = meta.get("date")
                    if club and date:
                        club_dates[club].add(date)
                except Exception as e:
                    print(f"Error parsing metadata for {session_name}: {e}")
        return {club: sorted(list(dates)) for club, dates in club_dates.items()}

    club_to_dates = load_club_dates()

    def on_club_selected():
        selected_club = club_selector.currentText()
        date_selector.clear()
        session_dropdown.clear()
        if selected_club in club_to_dates:
            date_selector.addItems(club_to_dates[selected_club])

    def on_date_selected():
        selected_club = club_selector.currentText()
        selected_date = date_selector.currentText()
        session_dropdown.clear()
        if not selected_club or not selected_date:
            return

        matching_sessions = [
            f for f in os.listdir(sessions_path)
            if os.path.isdir(os.path.join(sessions_path, f)) and
               selected_club in f and selected_date in f
        ]
        session_dropdown.addItems(sorted(matching_sessions))
        update_status_label()

    # -- paid / unpaid toggle ----------------------------------------
    def set_paid(paid: bool) -> None:
        sess = session_dropdown.currentText()
        mpath = meta_path(sess)
        if not os.path.exists(mpath):
            QMessageBox.warning(scr, "Error", "Metadata file not found.")
            return
        try:
            with open(mpath) as f:
                meta = json.load(f)
            meta["paid"] = paid
            with open(mpath, "w") as f:
                json.dump(meta, f, indent=4)
            update_status_label()
        except Exception as exc:
            QMessageBox.critical(scr, "Error", f"Failed to update metadata:\n{exc}")

    # -- delete with confirmation ------------------------------------
    def delete_session() -> None:
        sess = session_dropdown.currentText()
        if not sess:
            QMessageBox.warning(scr, "No Session Selected", "Select a session to delete.")
            return
        if QMessageBox.question(
            scr, "Confirm Deletion",
            f"Delete session '{sess}' permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            import shutil
            shutil.rmtree(os.path.join(sessions_path, sess))
            QMessageBox.information(scr, "Deleted", f"Session '{sess}' deleted.")
            on_date_selected()  # refresh session dropdown
        except Exception as exc:
            QMessageBox.critical(scr, "Error", f"Failed to delete session:\n{exc}")

    # Buttons
    row = QHBoxLayout()
    for text, func in [("Mark as Paid", lambda: set_paid(True)),
                       ("Mark as Unpaid", lambda: set_paid(False)),
                       ("Delete Session", delete_session)]:
        btn = QPushButton(text)
        btn.clicked.connect(func)
        row.addWidget(btn)

    refresh_btn = QPushButton("Refresh")
    def hard_refresh():
        nonlocal club_to_dates
        club_to_dates = load_club_dates()
        club_selector.setCurrentIndex(0)
        date_selector.clear()
        session_dropdown.clear()
        refresh_current_session_label()
        status_label.setText("Select a session to view or update its paid status.")
    refresh_btn.clicked.connect(hard_refresh)
    row.addWidget(refresh_btn)
    layout.addLayout(row)

    # Signal wiring
    club_selector.currentTextChanged.connect(on_club_selected)
    date_selector.currentTextChanged.connect(on_date_selected)
    session_dropdown.currentIndexChanged.connect(update_status_label)

    return scr

def create_current_session_files_tab(state: Dict) -> QWidget:
    scr = QWidget()
    scr_layout = QVBoxLayout(scr)

    header = QLabel("Files in Current Session")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    scr_layout.addWidget(header)

    file_dropdown = QComboBox()
    scr_layout.addWidget(file_dropdown)

    table = QTableWidget()
    scr_layout.addWidget(table)

    def load_csv_to_table(path: str):
        try:
            df = pd.read_csv(path)
        except Exception as e:
            table.setRowCount(0)
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels(["Error"])
            table.setItem(0, 0, QTableWidgetItem(f"Error loading CSV: {e}"))
            return

        table.setRowCount(len(df))
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels(df.columns.tolist())

        for i, row in df.iterrows():
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def refresh():
        file_dropdown.blockSignals(True)  # avoid firing currentIndexChanged during reset
        file_dropdown.clear()
        table.setRowCount(0)
        table.setColumnCount(0)

        current_session = state.get("current_session")
        if not current_session or not os.path.exists(current_session):
            file_dropdown.setEnabled(False)
            table.setColumnCount(1)
            table.setRowCount(1)
            table.setHorizontalHeaderLabels(["Notice"])
            table.setItem(0, 0, QTableWidgetItem("⚠️ No session created yet."))
            file_dropdown.blockSignals(False)
            return

        csv_dir = os.path.join(current_session, "csv")
        if not os.path.exists(csv_dir):
            file_dropdown.setEnabled(False)
            table.setColumnCount(1)
            table.setRowCount(1)
            table.setHorizontalHeaderLabels(["Notice"])
            table.setItem(0, 0, QTableWidgetItem("⚠️ No CSV directory in session."))
            file_dropdown.blockSignals(False)
            return

        filenames = sorted(f for f in os.listdir(csv_dir) if f.endswith(".csv"))
        if not filenames:
            file_dropdown.setEnabled(False)
            table.setColumnCount(1)
            table.setRowCount(1)
            table.setHorizontalHeaderLabels(["Notice"])
            table.setItem(0, 0, QTableWidgetItem("⚠️ No CSV files found."))
            file_dropdown.blockSignals(False)
            return

        file_dropdown.setEnabled(True)
        file_dropdown.addItems(filenames)

        def update_display(index):
            fname = file_dropdown.itemText(index)
            if fname:
                state["_last_selected_file"] = fname  # ⬅️ Save the selected file
                full_path = os.path.join(csv_dir, fname)
                load_csv_to_table(full_path)

        file_dropdown.currentIndexChanged.connect(update_display)

        # Try to re-select the previously selected file
        previously_selected = state.get("_last_selected_file")
        if previously_selected and previously_selected in filenames:
            idx = filenames.index(previously_selected)
        else:
            idx = 0  # default to first if none or invalid

        file_dropdown.setCurrentIndex(idx)
        update_display(idx)

        file_dropdown.blockSignals(False)

    scr.refresh = refresh
    return scr

from collections import defaultdict

def create_any_file_viewer_tab(state: Dict) -> QWidget:
    scr = QWidget()
    layout = QVBoxLayout(scr)

    header = QLabel("Browse Any Session File")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    club_dropdown = QComboBox()
    date_dropdown = QComboBox()
    file_dropdown = QComboBox()

    layout.addWidget(QLabel("Select Club:"))
    layout.addWidget(club_dropdown)
    layout.addWidget(QLabel("Select Date:"))
    layout.addWidget(date_dropdown)
    layout.addWidget(QLabel("Select File:"))
    layout.addWidget(file_dropdown)

    table = QTableWidget()
    layout.addWidget(table)

    def load_csv_to_table(path: str):
        try:
            df = pd.read_csv(path)
        except Exception as e:
            table.setRowCount(0)
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels(["Error"])
            table.setItem(0, 0, QTableWidgetItem(f"Error loading CSV: {e}"))
            return

        table.setRowCount(len(df))
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels(df.columns.tolist())

        for i, row in df.iterrows():
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def load_club_date_file_structure():
        structure = defaultdict(lambda: defaultdict(list))
        for session_name in os.listdir(SESSIONS_DIR):
            session_path = os.path.join(SESSIONS_DIR, session_name)
            meta_path = os.path.join(session_path, "metadata", "metadata.json")
            if not os.path.exists(meta_path):
                continue
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                club = meta.get("club")
                date = meta.get("date")
                csv_path = os.path.join(session_path, "csv")
                if club and date and os.path.exists(csv_path):
                    for f in os.listdir(csv_path):
                        if f.endswith(".csv"):
                            structure[club][date].append((session_path, f))
            except:
                continue
        return structure

    club_date_file_map = load_club_date_file_structure()

    def on_club_change():
        date_dropdown.clear()
        file_dropdown.clear()
        selected_club = club_dropdown.currentText()
        if selected_club in club_date_file_map:
            date_dropdown.addItems(sorted(club_date_file_map[selected_club].keys()))

    def on_date_change():
        file_dropdown.clear()
        selected_club = club_dropdown.currentText()
        selected_date = date_dropdown.currentText()
        if selected_club in club_date_file_map and selected_date in club_date_file_map[selected_club]:
            file_names = [f for (_, f) in club_date_file_map[selected_club][selected_date]]
            file_dropdown.addItems(file_names)

    def on_file_change():
        selected_club = club_dropdown.currentText()
        selected_date = date_dropdown.currentText()
        selected_file = file_dropdown.currentText()
        if not (selected_club and selected_date and selected_file):
            return
        for folder, fname in club_date_file_map[selected_club][selected_date]:
            if fname == selected_file:
                path = os.path.join(folder, "csv", fname)
                load_csv_to_table(path)
                break

    club_dropdown.addItems(sorted(club_date_file_map.keys()))
    club_dropdown.currentTextChanged.connect(on_club_change)
    date_dropdown.currentTextChanged.connect(on_date_change)
    file_dropdown.currentTextChanged.connect(on_file_change)

    return scr


# ---------------------------------------------------------------------
# Main window builder
# ---------------------------------------------------------------------

def create_main_window() -> QTabWidget:
    tabs = QTabWidget()
    state: Dict = {}
    state["global_metadata"] = load_global_metadata()


    tabs.addTab(create_program_flow_tab(state), "Program")
    tabs.addTab(create_flagged_sessions_tab(state), "Flagged")
    tabs.addTab(create_session_admin_tab(state), "Session Admin")
    tabs.addTab(create_current_session_files_tab(state), "Current Session Files")
    tabs.addTab(create_any_file_viewer_tab(state), "Browse All Files")


    return tabs


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)

    # ✅ Load stylesheet in a PyInstaller-safe way
    if getattr(sys, 'frozen', False):  # Running as .exe from PyInstaller
        base_path = sys._MEIPASS
    else:  # Running from source (e.g., VS Code)
        base_path = os.path.dirname(os.path.abspath(__file__))

    qss_path = os.path.join(base_path, "style.qss")
    try:
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Warning: Failed to load stylesheet ({qss_path}): {e}")

    window = create_main_window()

    # Hook up dynamic refresh
    def refresh_dynamic_tab(index):
        widget = window.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    window.currentChanged.connect(refresh_dynamic_tab)

    window.setWindowTitle("AnkleBreaker")
    window.resize(600, 450)
    window.show()
    sys.exit(app.exec())



if __name__ == "__main__":
    main()

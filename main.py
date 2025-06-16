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
    QButtonGroup,
)

# Ensure metadata.json exists in the current directory
ROOT_METADATA_PATH = os.path.join(os.getcwd(), "metadata.json")
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

#add duplicate protection!!!!!!!!!!


def create_session_creation_screen(stack: QStackedWidget, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)
    clubs = ["None"] + state["global_metadata"].get("clubs", [])

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
            base_session_name = f"Session-{club_name}-{date_str}"

            flagged = False
            flagged_files = []

            base_dir = os.getcwd()
            sessions_path = os.path.join(base_dir, "sessions")
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
            for df, desired_name in file_output:
                name_base = desired_name.rsplit(".csv", 1)[0]
                actual_filename = desired_name
                suffix = 2
                while actual_filename in written_filenames or os.path.exists(os.path.join(session_path, "csv", actual_filename)):
                    actual_filename = f"{name_base}-v{suffix}.csv"
                    suffix += 1
                written_filenames.add(actual_filename)
                df.to_csv(os.path.join(session_path, "csv", actual_filename), index=False)

            # Step 4: Write metadata
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
        if not new_club or new_club in clubs:
            return  # Do nothing if empty or already exists
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


    add_button = QPushButton("Add Club")
    add_button.clicked.connect(add_club)
    right_layout.addWidget(add_button)

    remove_button = QPushButton("Remove Club")
    remove_button.clicked.connect(remove_club)
    right_layout.addWidget(remove_button)

    main_layout.addLayout(left_layout, stretch=2)
    main_layout.addLayout(right_layout, stretch=1)

    return screen


from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QHBoxLayout, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt


from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QHBoxLayout, QScrollArea, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt
import os
import pandas as pd

def create_assign_status_screen(stack, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)

    # LEFT SIDE
    left_layout = QVBoxLayout()
    lbl = QLabel("Status Assignment (Index 2, Step 3)")
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

    # RIGHT SIDE - Other status display
    right_layout = QVBoxLayout()
    other_display = QTextEdit()
    other_display.setReadOnly(True)
    right_layout.addWidget(QLabel("People with status 'Other' (by file):"))
    right_layout.addWidget(other_display)

    # Detect most recent session folder
    sessions_dir = os.path.join(os.getcwd(), "sessions")
    latest_session = None
    if os.path.exists(sessions_dir):
        folders = [
            os.path.join(sessions_dir, f)
            for f in os.listdir(sessions_dir)
            if os.path.isdir(os.path.join(sessions_dir, f))
        ]
        if folders:
            latest_session = max(folders, key=os.path.getctime)

    session_csvs = []
    dataframes = []
    if latest_session:
        csv_dir = os.path.join(latest_session, "csv")
        if os.path.exists(csv_dir):
            for fname in os.listdir(csv_dir):
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

    def update_other_display():
        content = ""
        for fname, df in zip(session_csvs, dataframes):
            others = df[df["current_status"] == "other"]["Name"].tolist()
            if others:
                content += f"{fname}:\n"
                for name in others:
                    content += f"  {name}\n"
        other_display.setText(content.strip())

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
            statuses = ["regular", "manual", "comped", "refund", "other"]

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
                    return handler

                btn.clicked.connect(make_click_handler())
                button_group.addButton(btn)
                button_row.addWidget(btn)

            person_box.addLayout(button_row)
            wrapper = QFrame()
            wrapper.setLayout(person_box)
            wrapper.setFrameShape(QFrame.Shape.Box)
            scroll_layout.addWidget(wrapper)

    update_other_display()

    file_dropdown.addItems(session_csvs)
    file_dropdown.currentIndexChanged.connect(update_person_buttons)

    if dataframes:
        update_person_buttons(0)


    def go_to_fee_schedule():
        # Replace the placeholder with actual screen
        fee_screen = create_fee_schedule_screen(stack, state)
        stack.removeWidget(stack.widget(3))  # Remove placeholder
        stack.insertWidget(3, fee_screen)    # Insert real widget at index 3
        stack.setCurrentIndex(3)
    next_btn = QPushButton("Next")
    next_btn.clicked.connect(go_to_fee_schedule)



    left_layout.addWidget(next_btn)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(1))
    left_layout.addWidget(back_btn)

    main_layout.addLayout(left_layout, stretch=3)
    main_layout.addLayout(right_layout, stretch=1)

    return screen

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QHBoxLayout, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QHBoxLayout, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
import os

def create_fee_schedule_screen(stack, state) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)
    def event(e):
        if e.type() == e.Type.Show:
            populate_fee_inputs()
        return QWidget.event(screen, e)

    screen.event = event

    layout.addWidget(QLabel("Fee Schedule (Index 3, Step 4)"))
    
    fee_inputs = {}
    state["fee_schedule"] = {}  # Reset/init fee schedule in state

    validator = QIntValidator()
    validator.setBottom(1)
    def populate_fee_inputs():
        # Only populate if not already done
        if fee_inputs or not state.get("csv_paths"):
            return

        for path in state["csv_paths"]:
            filename = os.path.basename(path)
            input_field = QLineEdit()
            input_field.setValidator(validator)
            input_field.setPlaceholderText("Enter cost")
            file_form.addRow(QLabel(filename), input_field)
            fee_inputs[filename] = input_field


    # Debug: Show csv paths available
    csv_paths = state.get("csv_paths", [])
    print("Fee Schedule Screen: csv_paths =", csv_paths)

    file_form = QFormLayout() 

    if not csv_paths:
        layout.addWidget(QLabel("⚠️ No CSV files found in state."))
    else:
        for path in csv_paths:
            filename = os.path.basename(path)
            input_field = QLineEdit()
            input_field.setValidator(validator)
            input_field.setPlaceholderText("Enter cost")
            file_form.addRow(QLabel(filename), input_field)
            fee_inputs[filename] = input_field

    layout.addLayout(file_form)

    # Bulk assign
    layout.addWidget(QLabel("Bulk Assign to All:"))
    bulk_input = QLineEdit()
    bulk_input.setValidator(validator)
    bulk_input.setPlaceholderText("Enter fee to apply to all")
    layout.addWidget(bulk_input)

    def assign_all():
        value = bulk_input.text()
        if not value:
            return
        for field in fee_inputs.values():
            field.setText(value)

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

    # Navigation
    nav_row = QHBoxLayout()
    
    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(2))
    nav_row.addWidget(back_btn)

    def save_and_continue():
        for path in csv_paths:
            filename = os.path.basename(path)
            text = fee_inputs[filename].text()
            if text.isdigit():
                state["fee_schedule"][filename] = int(text)
        print("Fee schedule saved to state:", state["fee_schedule"])
        stack.setCurrentIndex(4)  # Placeholder for now

    next_btn = QPushButton("Next")
    next_btn.clicked.connect(save_and_continue)
    nav_row.addWidget(next_btn)

    layout.addLayout(nav_row)

    return screen



# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------

def create_program_flow_tab(state: Dict) -> QStackedWidget:
    stack = QStackedWidget()
    state["stack"] = stack  # 🔁 Store for future screen swaps

    stack.addWidget(create_welcome_screen(stack, state))         # 0
    stack.addWidget(create_session_creation_screen(stack, state)) # 1
    stack.addWidget(create_assign_status_screen(stack, state))    # 2

    placeholder = QWidget()  # Placeholder for lazy-loaded fee screen
    stack.addWidget(placeholder)  # 3
    return stack



from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt


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

        base_dir = os.getcwd()
        sessions_path = os.path.join(base_dir, "sessions")

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
    state["global_metadata"] = load_global_metadata()


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

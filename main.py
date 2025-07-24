import json
import os
import re
import shutil
import sys
import time

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Third-party imports
import pandas as pd

# PyQt6 imports
from PyQt6.QtCore import QDate, QObject, QEvent, Qt, QSize, pyqtSignal, QSettings, QCoreApplication
from PyQt6.QtGui import QAction, QIcon, QDoubleValidator, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QLayout,
    QMenu,
    QMessageBox,
    QPushButton,  
    QRadioButton,  
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

class SignalBus(QObject):
    sessionsChanged = pyqtSignal()
    clubsChanged = pyqtSignal()
    dataChanged = pyqtSignal()
    # Add more signals here as needed

class WheelEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            return True  # Block the wheel event
        return super().eventFilter(obj, event)

settings = QSettings("TrackitHub", "AnkleBreaker")

base_path = settings.value("base_path", str(Path.home() / "AnkleBreakerData"))
BASE_DIR = Path(base_path)
BASE_DIR.mkdir(parents=True, exist_ok=True)  # ✅ Make sure base folder exists

ROOT_METADATA_PATH = BASE_DIR / "metadata.json"
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

DEFAULT_CLUBS = ["Zorano"]
COMPED_NAMES = {
    "vincent robertson",
    "ryan marvin",
    "zorano tubo",
    "kaleta tubo",
    "tiniira tubo",
    "marena tubo",
    "cole hessler",
    "meyer knapp",
    "tina knapp",
    "anderson leclair",
    "the ghost"
}
STATUS_LIST = ["regular", "manual", "comped", "refund", "waitlist", "other"]

def write_metadata(meta_path: str, metadata: dict):
    """Writes a metadata dictionary to disk."""
    try:
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write metadata to {meta_path}: {e}")

def determine_default_status(notes: str, name: str) -> str:
    """Returns default status for a participant based on notes and name."""
    name_lower = str(name).strip().lower()
    if name_lower in COMPED_NAMES:
        return "comped"

    notes_lower = str(notes).lower()
    if "comped" in notes_lower:
        return "comped"
    elif "no capacity, and room on the waiting list : register" in notes_lower:
        return "waitlist"
    elif "refund" in notes_lower:
        return "refund"
    elif "manually confirmed by" in notes_lower:
        return "manual"
    elif "not over capacity: register" in notes_lower:
        return "regular"
    else:
        return "other"

def load_global_metadata() -> dict:
    if not os.path.exists(ROOT_METADATA_PATH):
        default_data = {"clubs": DEFAULT_CLUBS}
        with open(ROOT_METADATA_PATH, "w") as f:
            json.dump(default_data, f, indent=4)
        return default_data

    try:
        with open(ROOT_METADATA_PATH) as f:
            data = json.load(f)
            if "clubs" not in data:
                data["clubs"] = DEFAULT_CLUBS
                save_global_metadata(data)
            return data
    except Exception:
        # fallback: reset metadata file
        default_data = {"clubs": DEFAULT_CLUBS}
        with open(ROOT_METADATA_PATH, "w") as f:
            json.dump(default_data, f, indent=4)
        return default_data

def save_global_metadata(data: dict):
    with open(ROOT_METADATA_PATH, "w") as f:
        json.dump(data, f, indent=4)

def is_file_flagged(df: pd.DataFrame) -> bool:
    return "current_status" in df.columns and (df["current_status"] == "other").any()

def go_back_to_previous(state: Dict):
    tab_index = state.get("previous_tab_index", 0)
    screen_index = state.get("previous_screen_index", 0)
    state["tabs"].setCurrentIndex(tab_index)
    if tab_index == 0:
        state["stack"].setCurrentIndex(screen_index)

def go_back_to_program(state: Dict):
    state["tabs"].setCurrentIndex(0)  # Program tab
    screen_index = state.get("previous_program_screen", 0)
    state["stack"].setCurrentIndex(screen_index)

def load_club_dates() -> Dict[str, List[str]]:
    club_to_dates = {}
    for f in os.listdir(SESSIONS_DIR):
        session_path = os.path.join(SESSIONS_DIR, f)
        if not os.path.isdir(session_path):
            continue
        metadata_path = os.path.join(session_path, "metadata", "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path) as m:
                    data = json.load(m)
                    club = data.get("club")
                    date = data.get("date")
                    if club and date:
                        club_to_dates.setdefault(club, []).append(date)
            except Exception as e:
                print(f"[ERROR] Failed to read metadata for session {f}: {e}")
    return club_to_dates

def get_csv_paths_from_dir(csv_dir: str | Path) -> List[str]:
    if not os.path.isdir(csv_dir):
        return []
    return sorted([
        os.path.join(csv_dir, f)
        for f in os.listdir(csv_dir)
        if f.endswith(".csv")
    ])

def create_graphical_loader_screen(stack: QStackedWidget, state: Dict) -> QWidget:
    scr = QWidget()
    layout = QVBoxLayout(scr)
    layout.setSpacing(8)

    # Back to Welcome button (top-left)
    top_bar = QHBoxLayout()
    top_bar.setContentsMargins(10, 10, 10, 10)  # Add margin around the bar
    top_bar.setSpacing(12)                      # Add spacing between buttons


    back_to_previous_btn = QToolButton()
    back_to_previous_btn.setText("← Previous Screen")
    back_to_previous_btn.setObjectName("navBackButton")
    back_to_previous_btn.clicked.connect(lambda: go_back_to_previous(state))
    top_bar.addWidget(back_to_previous_btn)
    top_bar.addStretch()
    # Right: Back to Program button
    back_to_program_btn = QToolButton()
    back_to_program_btn.setText("Back to Program")
    back_to_program_btn.setObjectName("navBackButton")
    back_to_program_btn.clicked.connect(lambda: go_back_to_program(state))
    top_bar.addWidget(back_to_program_btn)
    layout.addLayout(top_bar)

    # Header
    # Secondary back button (between club and session views)
    back_btn = QToolButton()
    back_btn.setText("← Back")
    back_btn.setVisible(False)
    back_btn.setProperty("class", "folder-button")
    back_btn.style().unpolish(back_btn)
    back_btn.style().polish(back_btn)

    # Header and Back button in same row
    header = QLabel("Select a Club")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)

    header_layout = QHBoxLayout()
    header_layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
    header_layout.addStretch()
    header_layout.addWidget(header, alignment=Qt.AlignmentFlag.AlignCenter)
    header_layout.addStretch()
    layout.addLayout(header_layout)

    content_widget = QWidget()
    content_layout = QGridLayout(content_widget)
    layout.addWidget(content_widget)

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    tree.setVisible(False)
    layout.addWidget(tree)

    selected_session_label = QLabel("Selected Session: None")
    selected_session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(selected_session_label)

    admin_btn_layout = QHBoxLayout()
    mark_paid_btn = QPushButton("Mark Paid")
    mark_unpaid_btn = QPushButton("Mark Unpaid")
    delete_session_btn = QPushButton("Delete Session")
    for btn in [mark_paid_btn, mark_unpaid_btn, delete_session_btn]:
        btn.setEnabled(False)
        admin_btn_layout.addWidget(btn)
    layout.addLayout(admin_btn_layout)

    def extract_club_names():
        club_names = set()
        if not os.path.exists(SESSIONS_DIR):
            return []
        for folder in os.listdir(SESSIONS_DIR):
            parts = folder.split("-")
            if len(parts) >= 4 and parts[0] == "Session":
                club = parts[1]
                club_names.add(club)
        return sorted(club_names)

    def show_club_buttons():
        header.setText("Select a Club")
        back_btn.setVisible(False)
        back_to_previous_btn.setVisible(True)  # ✅ Show only at top-level
        back_to_program_btn.setVisible(True)
        content_widget.setVisible(True)
        tree.setVisible(False)

        for i in reversed(range(content_layout.count())):
            content_layout.itemAt(i).widget().setParent(None)

        club_names = extract_club_names()
        for idx, club in enumerate(club_names):
            btn = QToolButton()
            btn.setText(club)
            btn.setIcon(QIcon.fromTheme("folder"))
            btn.setIconSize(QSize(48, 48))
            btn.setFixedSize(120, 100)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setProperty("class", "folder-button")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.mouseDoubleClickEvent = lambda e, club=club: show_sessions_for_club(club)
            content_layout.addWidget(btn, idx // 4, idx % 4)

    def show_sessions_for_club(club: str):
        header.setText(f"Sessions for {club}")
        back_btn.setVisible(True)
        back_to_previous_btn.setVisible(False)  # ✅ Hide when inside a club
        back_to_program_btn.setVisible(False)
        content_widget.setVisible(False)
        tree.setVisible(True)

        tree.clear()
        for folder in sorted(os.listdir(SESSIONS_DIR)):
            parts = folder.split("-")
            if len(parts) >= 4 and parts[0] == "Session" and parts[1] == club:
                session_path = os.path.join(SESSIONS_DIR, folder)
                meta_path = os.path.join(session_path, "metadata", "metadata.json")
                csv_path = os.path.join(session_path, "csv")
                if not os.path.exists(meta_path) or not os.path.exists(csv_path):
                    continue
                try:
                    with open(meta_path, "r") as f:
                        metadata = json.load(f)
                    paid_status = metadata.get("paid", False)
                    status_str = "paid ✅" if paid_status else "unpaid ❌"
                    net = metadata.get("net_to_club", None)
                    formatted_total = f"${net:.2f}" if isinstance(net, (int, float)) else "No total yet"
                    display_name = f"{folder} — {status_str} — total {formatted_total}"
                except Exception as e:
                    print(f"[ERROR] Could not read metadata for {folder}: {e}")
                    display_name = folder
                parent_item = QTreeWidgetItem([display_name])
                parent_item.setData(0, Qt.ItemDataRole.UserRole, session_path)
                for fname in sorted(os.listdir(csv_path)):
                    if fname.endswith(".csv"):
                        QTreeWidgetItem(parent_item, [fname])
                tree.addTopLevelItem(parent_item)

    def on_tree_item_clicked(item: QTreeWidgetItem, _):
        text = item.text(0)
        if "—" in text:
            session_name = text.split(" — ")[0]
            session_path = os.path.join(SESSIONS_DIR, session_name)
            state["_selected_session_path"] = session_path
            selected_session_label.setText(f"Selected Session: {session_name}")
            for btn in [mark_paid_btn, mark_unpaid_btn, delete_session_btn]:
                btn.setEnabled(True)
        else:
            state["_selected_session_path"] = None
            for btn in [mark_paid_btn, mark_unpaid_btn, delete_session_btn]:
                btn.setEnabled(False)

    tree.itemClicked.connect(on_tree_item_clicked)
    def confirm_and_load_session(item):
        session_path = item.data(0, Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            scr,
            "Load Session",
            f"Are you sure you want to load this session?\n\n{session_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            update_last_opened_metadata(session_path)
            load_session_from_folder(session_path, stack, state, scr)

    tree.itemDoubleClicked.connect(lambda item, _: confirm_and_load_session(item))

    def on_session_selected(item, _):
        session_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not session_path:
            return
        selected_session_label.setText(f"Selected Session: {os.path.basename(session_path)}")
        mark_paid_btn.setEnabled(True)
        mark_unpaid_btn.setEnabled(True)
        delete_session_btn.setEnabled(True)
        selected_session_label.session_path = session_path

    tree.itemClicked.connect(on_session_selected)

    def update_paid_status(path, status: bool):
        try:
            meta_path = os.path.join(path, "metadata", "metadata.json")
            with open(meta_path, "r") as f:
                metadata = json.load(f)
            metadata["paid"] = status
            write_metadata(meta_path, metadata)

            QMessageBox.information(scr, "Success", f"Session marked as {'paid' if status else 'unpaid'}.")
            show_sessions_for_club(header.text().split("Sessions for ")[-1])
        except Exception as e:
            QMessageBox.critical(scr, "Error", f"Failed to update paid status: {e}")
        state["signals"].sessionsChanged.emit()

    def delete_session(path):
        confirm = QMessageBox.question(
            scr,
            "Delete Session",
            f"Are you sure you want to permanently delete:\n\n{os.path.basename(path)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(path)
                if str(path) == str(state.get("current_session")):
                    print("🧹 Cleaning up: current session was just deleted")
                    state["current_session"] = None
                    if state.get("_welcome_next_btn"):
                        state["_welcome_next_btn"].setEnabled(False)

                    state["session_deleted"] = True
                    state["session_created"] = False
                    state["csv_paths"] = []
                    state["dataframes"] = {}
                    state["status_counts"] = {}
                    state["fee_schedule"] = {}

                    if state.get("_create_next_btn"):
                        state["_create_next_btn"].setEnabled(False)

                    if state.get("_upload_files_btn"):
                        state["_upload_files_btn"].setEnabled(True)
                    if state.get("_upload_folder_btn"):
                        state["_upload_folder_btn"].setEnabled(True)

                    if state.get("_welcome_next_btn"):
                        state["_welcome_next_btn"].setEnabled(False)

                    if state.get("_current_session_label"):
                        state["_current_session_label"].setText("Current Session: None")

                    if "refresh_current_session_label" in state and callable(state["refresh_current_session_label"]):
                        state["refresh_current_session_label"]()

                    # (Optional) Fallback: search upward for attached label and reset
                    parent = scr
                    while parent is not None:
                        if hasattr(parent, "current_session_label"):
                            parent.current_session_label.setText("No current session")
                            break
                        parent = parent.parent()

                    # ✅ Reset welcome screen if the deleted session was active there too
                    if state.get("session_path") == path:
                        state.pop("session_path", None)
                        state.pop("csv_paths", None)
                        state.pop("dataframes", None)
                        state.pop("df", None)

                        if "_welcome_file_label" in state:
                            state["_welcome_file_label"].setText("No files selected.")
                        if "_welcome_file_names_label" in state:
                            state["_welcome_file_names_label"].setText("")

                QMessageBox.information(scr, "Deleted", "Session deleted successfully.")
                selected_session_label.setText("Selected Session: None")
                for btn in [mark_paid_btn, mark_unpaid_btn, delete_session_btn]:
                    btn.setEnabled(False)
                state["_selected_session_path"] = None
                state["signals"].sessionsChanged.emit()
                show_sessions_for_club(header.text().split("Sessions for ")[-1])
                # 🔁 Recreate the Welcome screen so its labels are properly reset
                if "stack" in state:
                    new_welcome = create_welcome_screen(state["stack"], state)
                    state["stack"].removeWidget(state["stack"].widget(0))  # Remove old welcome
                    state["stack"].insertWidget(0, new_welcome)            # Insert new one

            except Exception as e:
                QMessageBox.critical(scr, "Error", f"Could not delete session: {e}")

    mark_paid_btn.clicked.connect(lambda: update_paid_status(selected_session_label.session_path, True))
    mark_unpaid_btn.clicked.connect(lambda: update_paid_status(selected_session_label.session_path, False))
    delete_session_btn.clicked.connect(lambda: delete_session(selected_session_label.session_path))
    

    back_btn.clicked.connect(show_club_buttons)
    show_club_buttons()
    scr.is_graphical_loader = True
    return scr

def update_last_opened_metadata(session_path: str):
        meta_path = os.path.join(session_path, "metadata", "metadata.json")
        try:
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            metadata["last_opened"] = datetime.now().isoformat()
            os.makedirs(os.path.dirname(meta_path), exist_ok=True)
            write_metadata(meta_path, metadata)

        except Exception as e:
            print(f"[ERROR] Could not update last_opened for {session_path}: {e}")

# ---------------------------------------------------------------------
# Screens for Program Flow Tab
# ---------------------------------------------------------------------

#This is the first screen that the user sees
def create_welcome_screen(stack: QStackedWidget, state: Dict) -> QWidget:

    screen = QWidget()
    layout = QVBoxLayout(screen)

    top_row = QHBoxLayout()

    label = QLabel("Welcome to the AnkleBreaker")
    label.setAlignment(Qt.AlignmentFlag.AlignLeft)

    next_btn = QPushButton("Next")
    state["_welcome_next_btn"] = next_btn

    next_btn.setEnabled(False)
    next_btn.setFixedWidth(150)

    top_row.addWidget(label)
    top_row.addStretch()
    top_row.addWidget(next_btn)

    layout.addLayout(top_row)

    file_label = QLabel("No files selected.")
    layout.addWidget(file_label)

    file_names_label = QLabel("")
    file_names_label.setWordWrap(True)
    layout.addWidget(file_names_label)

    state["_welcome_file_label"] = file_label
    state["_welcome_file_names_label"] = file_names_label

    select_files_btn = QPushButton("Select CSV Files")
    select_folder_btn = QPushButton("Select Folder")
    layout.addWidget(select_files_btn)
    layout.addWidget(select_folder_btn)
    state["_upload_files_btn"] = select_files_btn
    state["_upload_folder_btn"] = select_folder_btn

    graphical_loader_btn = QPushButton("Past Club Sessions")
    layout.addWidget(graphical_loader_btn)
    

    next_btn.clicked.connect(lambda: stack.setCurrentIndex(1))

    def open_graphical_loader():
        state["previous_screen_index"] = stack.currentIndex()
        state["previous_program_screen"] = stack.currentIndex()
        scr = create_graphical_loader_screen(stack, state)
        stack.addWidget(scr)
        stack.setCurrentWidget(scr)

    graphical_loader_btn.clicked.connect(open_graphical_loader)

    # Track last opened timestamp
    def update_last_opened_metadata(session_path: str):
        meta_path = os.path.join(session_path, "metadata", "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {}
        metadata["last_opened"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        write_metadata(meta_path, metadata)

    
    def load_paths(paths: List[str]):
        state["csv_paths"] = paths
        dfs, errors, warned_files = [], [], []

        for p in paths:
            try:
                df = pd.read_csv(p)
                headers = [c.strip().lower() for c in df.columns]

                # Expected layouts (processed or raw)
                processed_layout = ["name", "email", "phone number", "status", "registration time", "notes", "default_status", "anklebreaker notes", "current_status"]
                raw_layout = ["name", "email", "status", "registered", "notes"]

                if headers == processed_layout:
                    dfs.append(df)  # Already processed
                elif headers == raw_layout:
                    df = pd.read_csv(p, skiprows=1, header=None)
                    df.columns = ["Name", "Email", "Phone Number", "Status", "Registration Time", "Notes"]
                    df["default_status"] = df.apply(lambda row: determine_default_status(row["Notes"], row["Name"]), axis=1)
                    df["AnkleBreaker notes"] = ""
                    df["current_status"] = df["default_status"]
                    dfs.append(df)
                else:
                    warned_files.append(os.path.basename(p))
                    df = pd.read_csv(p, skiprows=1, header=None)
                    df.columns = ["Name", "Email", "Phone Number", "Status", "Registration Time", "Notes"]
                    df["default_status"] = df.apply(lambda row: determine_default_status(row["Notes"], row["Name"]), axis=1)
                    df["AnkleBreaker notes"] = ""
                    df["current_status"] = df["default_status"]
                    dfs.append(df)

            except Exception as exc:
                errors.append(f"{p}: {exc}")

        state["dataframes"] = dfs
        state["df"] = pd.concat(dfs, ignore_index=True) if dfs else None

        file_names = [os.path.basename(p) for p in paths]
        msg = f"Loaded {len(dfs)} file(s)"
        if errors:
            msg += f" ( {len(errors)} failed )"
        file_label.setText(msg)
        file_names_label.setText("Files:\n" + "\n".join(file_names))

        next_btn.setEnabled(len(dfs) > 0)

        if warned_files:
            QMessageBox.warning(
                screen,
                "Unexpected Headers",
                "The following file(s) do not have expected headers and were still loaded:\n\n" +
                "\n".join(warned_files)
            )

    def select_files():
        paths, _ = QFileDialog.getOpenFileNames(
            screen,
            "Select CSV Files",
            str(Path.home() / "Downloads"),  # 👈 Set initial dir
            "CSV Files (*.csv);;All Files (*)"
            )

        if not paths:
            return

        csv_paths = [p for p in paths if p.lower().endswith(".csv")]
        non_csv_paths = [p for p in paths if not p.lower().endswith(".csv")]

        if non_csv_paths:
            QMessageBox.information(
                screen,
                "Non-CSV Files Ignored",
                f"The following file(s) were ignored because they are not CSVs:\n\n" +
                "\n".join(non_csv_paths)
            )

        if not csv_paths:
            QMessageBox.warning(screen, "No CSV Files", "No valid CSV files were selected.")
            return

        load_paths(csv_paths)
        
    def select_folder():
        start_dir = str(SESSIONS_DIR) if os.path.exists(SESSIONS_DIR) else str(BASE_DIR)
        folder = QFileDialog.getExistingDirectory(
            screen,
            "Select Folder Containing CSV Files",
            str(Path.home() / "Downloads")  # 👈 Set initial dir
        )

        if not folder:
            return

        all_files = [os.path.join(folder, f) for f in os.listdir(folder)]
        csv_paths = [f for f in all_files if f.lower().endswith(".csv")]
        non_csv_paths = [f for f in all_files if not f.lower().endswith(".csv")]

        if non_csv_paths:
            QMessageBox.information(
                screen,
                "Non-CSV Files Ignored",
                f"The following file(s) were ignored because they are not CSVs:\n\n" +
                "\n".join(non_csv_paths)
            )

        if not csv_paths:
            QMessageBox.warning(screen, "No CSV Files", "The selected folder contains no CSV files.")
            return

        load_paths(csv_paths)

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addWidget(QLabel("Browse Recent Sessions:"))
    layout.addWidget(tree)

    def refresh_session_tree():
        tree.clear()
        if not os.path.exists(SESSIONS_DIR):
            return

        sessions_with_time = []
        for session_name in os.listdir(SESSIONS_DIR):
            session_path = os.path.join(SESSIONS_DIR, session_name)
            meta_path = os.path.join(session_path, "metadata", "metadata.json")
            if not os.path.exists(meta_path):
                continue
            with open(meta_path, "r") as f:
                metadata = json.load(f)
            last_opened = metadata.get("last_opened", "1970-01-01T00:00:00")
            sessions_with_time.append((session_name, last_opened))

        sessions_with_time.sort(
            key=lambda x: datetime.fromisoformat(x[1]) if isinstance(x[1], str) else datetime.min,
            reverse=True
        )

        for session_name, _ in sessions_with_time:
            session_path = os.path.join(SESSIONS_DIR, session_name)
            meta_path = os.path.join(session_path, "metadata", "metadata.json")
            csv_path = os.path.join(session_path, "csv")
            with open(meta_path, "r") as f:
                metadata = json.load(f)
            paid_status = metadata.get("paid", False)

            status_text = "paid ✅" if paid_status else "unpaid ❌"
            net_total = metadata.get("net_to_club", "No total yet")
            formatted_total = f"${net_total:.2f}" if isinstance(net_total, (int, float)) else "No total yet"
            display_name = f"{session_name} — {status_text} — Total: {formatted_total}"


            parent_item = QTreeWidgetItem([display_name])

            if not os.path.exists(csv_path):
                continue

            files = [
                (fname, os.path.getmtime(os.path.join(csv_path, fname)))
                for fname in os.listdir(csv_path)
                if fname.endswith(".csv")
            ]
            files.sort(key=lambda x: x[1], reverse=True)

            for fname, _ in files:
                QTreeWidgetItem(parent_item, [fname])
            tree.addTopLevelItem(parent_item)

    def confirm_and_load_session(session_dir):
        reply = QMessageBox.question(
            screen,
            "Load Session",
            f"Are you sure you want to load this session?\n\n{session_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            update_last_opened_metadata(session_dir)
            load_session_from_folder(session_dir, stack, state, screen)

    tree.itemDoubleClicked.connect(
        lambda item, _: confirm_and_load_session(os.path.join(SESSIONS_DIR, item.text(0).split(" — ")[0]))
    )

    refresh_session_tree()
    state["signals"].sessionsChanged.connect(refresh_session_tree)

    select_files_btn.clicked.connect(select_files)
    select_folder_btn.clicked.connect(select_folder)
    screen.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    return screen

#This is the second screen that the user sees and after clicking next is the point of no return
def create_session_creation_screen(stack: QStackedWidget, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)
    state["_wheel_filter"] = state.get("_wheel_filter") or WheelEventFilter()

    # LEFT SIDE
    left_layout = QVBoxLayout()
    lbl = QLabel("Session Creation")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    left_layout.addWidget(lbl)

    date_wid = QDateEdit()
    date_wid.setCalendarPopup(True)
    date_wid.setDisplayFormat("MMMM d, yyyy")
    date_wid.setDate(QDate.currentDate())
    left_layout.addWidget(date_wid)

    date_label = QLabel(f"Selected date: {date_wid.date().toString('MMMM d, yyyy')}")
    left_layout.addWidget(date_label)

    status_date = QLabel("Date selected: ✅")
    status_club = QLabel("Club selected: ❌")
    status_ready = QLabel("Ready to create session: ❌")
    left_layout.addWidget(status_date)
    left_layout.addWidget(status_club)
    left_layout.addWidget(status_ready)

    club_selector = QComboBox()
    
    left_layout.addWidget(club_selector)
    club_selector.installEventFilter(state["_wheel_filter"])

    # Row for Create and Remove buttons
    action_row = QHBoxLayout()
    create_btn = QPushButton("Create Session")
    create_btn.setEnabled(False)
    action_row.addWidget(create_btn)

    remove_club_btn = QPushButton("Remove Club")
    action_row.addWidget(remove_club_btn)

    left_layout.addLayout(action_row)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(0))
    left_layout.addWidget(back_btn)

    date_selected = True

    def update_status():
        club_selected = club_selector.currentText() != "None"
        status_date.setText(f"Date selected: {'✅' if date_selected else '❌'}")
        status_club.setText(f"Club selected: {'✅' if club_selected else '❌'}")
        ready = date_selected and club_selected
        status_ready.setText(f"Ready to create session: {'✅' if ready else '❌'}")
        create_btn.setEnabled(ready)

    def on_date_changed(new_date):
        nonlocal date_selected
        date_selected = True
        date_label.setText("Selected date: " + new_date.toString("MMMM d, yyyy"))
        update_status()

    date_wid.calendarWidget().clicked.connect(on_date_changed)
    date_wid.dateChanged.connect(on_date_changed)
    club_selector.currentTextChanged.connect(lambda _: update_status())

    # Populate from global metadata
    def refresh_dropdown():
        club_selector.blockSignals(True)
        club_selector.clear()
        clubs = ["None"] + state["global_metadata"].get("clubs", [])
        club_selector.addItems(clubs)
        club_selector.setCurrentIndex(0)
        club_selector.blockSignals(False)
        update_status()

    # Attach refresh to signal
    state["signals"].clubsChanged.connect(refresh_dropdown)

    refresh_dropdown()

    def show_confirmation_dialog():
        club_name = club_selector.currentText()
        date_str = date_wid.date().toString("yyyy-MM-dd")
        session_name = f"Session-{club_name}-{date_str}"
        file_names = [os.path.basename(p) for p in state.get("csv_paths", [])]

        dialog = QDialog()
        dialog.setWindowTitle("Confirm Session Creation")
        layout = QVBoxLayout(dialog)

        info = f"You are about to create a session.\n\n"
        info += f"Name: {session_name}\n"
        info += f"Files: {', '.join(file_names)}"
        label = QLabel(info)
        label.setWordWrap(True)
        layout.addWidget(label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(lambda: (dialog.accept(), create_session()))
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def create_session():
        club_name = club_selector.currentText()
        date_str = date_wid.date().toString("yyyy-MM-dd")
        base_session_name = f"Session-{club_name}-{date_str}"
        flagged = False
        flagged_files = []

        state["session_created"] = True
        state["session_deleted"] = False
        
        session_name = base_session_name
        suffix = 2
        session_path = SESSIONS_DIR / session_name
        while session_path.exists():
            session_name = f"{base_session_name}-v{suffix}"
            session_path = SESSIONS_DIR / session_name
            suffix += 1

        csv_dir = session_path / "csv"
        metadata_dir = session_path / "metadata"
        csv_dir.mkdir(parents=True)
        metadata_dir.mkdir(parents=True)

        new_paths = []
        for i, (df, original_path) in enumerate(zip(state["dataframes"], state["csv_paths"])):
            filename = os.path.basename(original_path)

            if "default_status" not in df.columns:
                df["default_status"] = df.apply(lambda row: determine_default_status(row["Notes"], row["Name"]), axis=1)

            if "current_status" not in df.columns:
                df["current_status"] = df["default_status"]

            if any(df["current_status"] == "other"):
                flagged = True
                if not filename.endswith("-flag.csv"):
                    filename = filename.replace(".csv", "-flag.csv")

            new_path = csv_dir / filename
            df.to_csv(new_path, index=False)
            new_paths.append(str(new_path))

            if filename.endswith("-flag.csv"):
                flagged_files.append(filename)

        if flagged and "-flag" not in session_name:
            session_name += "-flag"
            final_session_path = SESSIONS_DIR / session_name
            suffix = 2
            while final_session_path.exists():
                session_name = f"{session_name}-v{suffix}"
                final_session_path = SESSIONS_DIR / session_name
                suffix += 1

            os.rename(session_path, final_session_path)
            new_paths = [str(final_session_path / "csv" / os.path.basename(p)) for p in new_paths]
            session_path = final_session_path
            state["csv_paths"] = new_paths

        metadata = {
            "club": club_name,
            "date": date_str,
            "last_opened": datetime.now().isoformat(),
            "flagged": flagged,
            "flagged_files": flagged_files,
            "fees": {},
        }

        metadata_path = session_path / "metadata" / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)

        state["current_session"] = str(session_path)
        state["csv_paths"] = new_paths

        # Force rebuild of dataframes to avoid UI issues
        rebuilt_dataframes = {}
        for p in new_paths:
            try:
                df = pd.read_csv(p)
                if "default_status" not in df.columns:
                    df["default_status"] = df.apply(lambda row: determine_default_status(row["Notes"], row["Name"]), axis=1)
                if "current_status" not in df.columns:
                    df["current_status"] = df["default_status"]
                if "AnkleBreaker notes" not in df.columns:
                    df["AnkleBreaker notes"] = ""
                rebuilt_dataframes[p] = df
            except Exception as e:
                print(f"[ERROR] Failed to rebuild df from {p}: {e}")

        state["dataframes"] = rebuilt_dataframes

        for fn in state.get("_refresh_crud_banners", []):
            fn()
        state["signals"].sessionsChanged.emit()
        state["signals"].dataChanged.emit()
        state["session_locked"] = True
        # Disable upload buttons once session is locked
        if state.get("_upload_files_btn"):
            state["_upload_files_btn"].setEnabled(False)
        if state.get("_upload_folder_btn"):
            state["_upload_folder_btn"].setEnabled(False)

        # Rebuild assign screen but DO NOT switch to it
        # Rebuild assign screen AND switch to it
        assign_screen = create_assign_status_screen(stack, state)
        stack.removeWidget(stack.widget(2))
        stack.insertWidget(2, assign_screen)
        stack.setCurrentIndex(2)

        create_btn.setEnabled(False)  # ⛔ Prevent creating again without reset

    create_btn.clicked.connect(show_confirmation_dialog)

    # ---------------- Right side: Add Club ------------------------
    right_group = QGroupBox("Club Management")
    right_layout = QFormLayout(right_group)

    club_input = QLineEdit()
    club_input.setPlaceholderText("Enter club name")
    right_layout.addRow(QLabel("Club Name:"), club_input)

    add_button = QPushButton("Add Club")
    right_layout.addWidget(add_button)

    def add_club():
        new_club = club_input.text().strip()
        if not new_club or new_club in state["global_metadata"].get("clubs", []):
            return
        state["global_metadata"].get("clubs", []).append(new_club)
        save_global_metadata(state["global_metadata"])
        club_input.clear()
        state["signals"].clubsChanged.emit()

    def remove_selected_club():
        selected = club_selector.currentText()
        if selected in ["None", "Zorano"]:
            QMessageBox.information(screen, "Not Allowed", f"'{selected}' cannot be removed.")
            return

        confirm = QMessageBox.question(
            screen,
            "Confirm Club Removal",
            f"Are you sure you want to remove the club '{selected}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        if selected in state["global_metadata"].get("clubs", []):
            state["global_metadata"].get("clubs", []).remove(selected)
            save_global_metadata(state["global_metadata"])
            state["signals"].clubsChanged.emit()

    add_button.clicked.connect(add_club)
    remove_club_btn.clicked.connect(remove_selected_club)

    main_layout.addLayout(left_layout, stretch=2)
    main_layout.addWidget(right_group, stretch=1)

    return screen

#This is the third scrren that the user sees and is the first step after a session is created
#A user cannot backtrack past this screen
def create_assign_status_screen(stack, state) -> QWidget:
    # Completely replace scroll content and layout
    screen = QWidget()
    main_layout = QHBoxLayout(screen)

    session_csvs = []
    dataframes = []
    state["_wheel_filter"] = state.get("_wheel_filter") or WheelEventFilter()

    # Left layout
    left_layout = QVBoxLayout()

    file_dropdown = QComboBox()
    file_dropdown.installEventFilter(state["_wheel_filter"])

    def make_scroll_content():
        container = QWidget()
        layout = QVBoxLayout(container)
        container.setLayout(layout)
        container.setMinimumWidth(760)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return container, layout

    
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll_content, scroll_layout = make_scroll_content()
    scroll.setWidget(scroll_content)
    status_table = QTableWidget()
    status_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    status_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)




    
    def populate_file_dropdown(file_dropdown: QComboBox, state: Dict, session_csvs: List[str], dataframes: List[pd.DataFrame]):
        current_index = file_dropdown.currentIndex()
        selected_text = file_dropdown.currentText()

        # Clear + rebuild
        file_dropdown.blockSignals(True)
        file_dropdown.clear()
        file_dropdown.addItem("View All")

        session_csvs[:] = [os.path.basename(p) for p in state["csv_paths"]]
        dataframes[:] = [state["dataframes"][p] for p in state["csv_paths"]]
        file_dropdown.addItems(session_csvs)

        # Restore selection
        if selected_text == "View All":
            file_dropdown.setCurrentText("View All")
        elif selected_text in session_csvs:
            index = session_csvs.index(selected_text) + 1
            file_dropdown.setCurrentIndex(index)
        else:
            file_dropdown.setCurrentIndex(0)

        file_dropdown.blockSignals(False)

    file_dropdown_row = QHBoxLayout()
    file_dropdown.setContentsMargins(0, 0, 0, 0)

    file_dropdown.setFixedWidth(600)
    file_dropdown_row.addWidget(file_dropdown)

    # Add a small fixed spacer
    spacer = QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
    file_dropdown_row.addItem(spacer)

    file_dropdown_row.addStretch()  # Optional: keep this if you want the button to still shift right on window resize

    

    # 👇 Key line for consistency
    scroll_content.setMinimumWidth(760)  # or whatever matches View All layout width
    scroll_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    file_dropdown_container = QWidget()
    file_dropdown_container.setLayout(file_dropdown_row)
    file_dropdown_container.setContentsMargins(0, 0, 0, 0)

    left_layout.addWidget(file_dropdown_container)
    left_layout.addWidget(scroll)
    left_layout.setSpacing(6)  # optional: reduce vertical spacing

    
    next_btn = QPushButton("Next")
    left_layout.addWidget(next_btn)

    # Right layout (Other display)
    # Right layout: vertical split of top row (other + legend) and bottom row (status table)
    right_layout = QVBoxLayout()
    main_layout.setSpacing(12)
    main_layout.setContentsMargins(8, 8, 8, 8)
    right_layout.setSpacing(6)

    # Top row: horizontal layout of other_display and notes legend
    top_right_row = QHBoxLayout()

    # Left: People with status 'Other'
    left_half = QVBoxLayout()
    left_half.addWidget(QLabel("People with 'Other'"))
    other_display = QTextEdit()
    other_display.setFixedWidth(250)
    other_display.setReadOnly(True)
    left_half.addWidget(other_display)

    # Right: Notes Legend
    right_half = QVBoxLayout()
    right_half.addWidget(QLabel("Notes Legend:"))
    legend_text = QTextEdit()
    legend_text.setReadOnly(True)
    legend_text.setPlainText(
        "• Contains 'comped' → Status: Comped\n"
        "• Contains 'no capacity, and room on the waiting list : register' → Waitlist\n"
        "• Contains 'refund' → Refund\n"
        "• Contains 'manually confirmed by' → Manual\n"
        "• Contains 'not over capacity: register' → Regular\n"
        "• Anything else → Other\n"
        "• PayPal issue? → Regular\n"
        "• Paid cash? → Manual"
    )
    right_half.addWidget(legend_text)

    top_right_row.addLayout(left_half, 1)
    top_right_row.addLayout(right_half, 1)

    # Add top row and bottom status table to the right layout
    # Add top row (other + legend) and bottom table
    right_layout.addLayout(top_right_row)
    right_layout.addSpacing(12)  # Optional: spacing between top and table
    right_layout.addWidget(QLabel("Status Counts by File:"))
    right_layout.addWidget(status_table)






    # Get current session folder
    current_session = state.get("current_session")
    # Force-rebuild csv_paths using current session folder, not stale copy
    csv_paths = []
    session_path = state.get("current_session")
    if not session_path:
        return screen  # Or show an error, or skip loading

    csv_dir = os.path.join(session_path, "csv")

    csv_paths = get_csv_paths_from_dir(csv_dir)
    state["csv_paths"] = csv_paths

    dataframes_dict = state.get("dataframes", {})

    # NEW: Try using state values if already populated
    if csv_paths and isinstance(dataframes_dict, dict) and all(p in dataframes_dict for p in csv_paths):
        session_csvs.clear()
        dataframes.clear()
        session_csvs.extend([os.path.basename(p) for p in csv_paths])
        dataframes.extend([dataframes_dict[p] for p in csv_paths])
    else:
        session_csvs.clear()
        dataframes.clear()

        # Fallback to loading from disk
        if current_session and os.path.exists(current_session):
            csv_dir = os.path.join(current_session, "csv")
        else:
            folders = [
                os.path.join(SESSIONS_DIR, f)
                for f in os.listdir(SESSIONS_DIR)
                if os.path.isdir(os.path.join(SESSIONS_DIR, f))
            ]
            latest_session = max(folders, key=os.path.getctime, default=None)
            csv_dir = os.path.join(latest_session, "csv") if latest_session else None

        if csv_dir and os.path.exists(csv_dir):
            for path in get_csv_paths_from_dir(csv_dir):
                if path.endswith(".csv"):
                    path = os.path.join(csv_dir, path)
                    df = pd.read_csv(path)
                    if "default_status" in df.columns:
                        if "current_status" not in df.columns:
                            df["current_status"] = df["default_status"]
                        if path not in csv_paths:
                            dataframes.append(df)
                            session_csvs.append(path)
                            dataframes_dict[path] = df

        state["csv_paths"] = csv_paths
        state["dataframes"] = dataframes_dict
    # Now continue with original function logic...
    state["status_counts"] = {}
    def propagate_file_rename(old_path: str, new_path: str, state: Dict, stack: QStackedWidget):
                    old_fname = os.path.basename(old_path)
                    new_fname = os.path.basename(new_path)

                    # Update csv_paths
                    state["csv_paths"] = [new_path if p == old_path else p for p in state["csv_paths"]]

                    # Update dataframes
                    if old_path in state["dataframes"]:
                        state["dataframes"][new_path] = state["dataframes"].pop(old_path)

                    # Update status_counts
                    if "status_counts" in state and old_fname in state["status_counts"]:
                        state["status_counts"][new_fname] = state["status_counts"].pop(old_fname)

                    # Update fee_schedule
                    if "fee_schedule" in state and old_fname in state["fee_schedule"]:
                        state["fee_schedule"][new_fname] = state["fee_schedule"].pop(old_fname)
                    # Refresh screens
                    for screen_index in [2, 3, 4]:
                        widget = stack.widget(screen_index)

                        if screen_index == 2:
                            assign_screen = state.get("assign_status_screen")
                            if assign_screen and hasattr(assign_screen, "refresh_file_dropdown"):
                                assign_screen.refresh_file_dropdown()
                        elif screen_index == 3:
                            new_screen = create_fee_schedule_screen(stack, state)
                            stack.removeWidget(widget)
                            stack.insertWidget(3, new_screen)
                        elif screen_index == 4:
                            summary_screen = create_payment_summary_screen(stack, state)
                            stack.removeWidget(stack.widget(4))
                            stack.insertWidget(4, summary_screen)
                    # Emit signal to trigger any reactive UI
                    state["signals"].sessionsChanged.emit()  # ✅ triggers QTreeWidgets
                    state["signals"].dataChanged.emit()

    def update_flag_state_for_file(csv_path, state, stack):
        # Step 0: Normalize csv_path to match real path in state
        for p in state["csv_paths"]:
            if os.path.basename(p) == os.path.basename(csv_path):
                csv_path = p
                break

        df = state["dataframes"].get(csv_path)
        if df is None:
            print("[WARNING] No dataframe found for path:", csv_path)
            return

        still_flagged = (df["current_status"] == "other").any()
        is_flagged_file = "-flag.csv" in os.path.basename(csv_path)
        if not is_flagged_file or still_flagged:
            return  # Nothing to do

        # Paths and names
        old_basename = os.path.basename(csv_path)
        unflagged_path = re.sub(r"-flag(?=\.csv$)", "", csv_path)
        new_basename = os.path.basename(unflagged_path)
        session_path = os.path.dirname(os.path.dirname(csv_path))
        original_session = state.get("current_session")
        meta_path = os.path.join(session_path, "metadata", "metadata.json")

        # Load metadata
        metadata = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                metadata = json.load(f)

        # Access check
        if not (os.path.exists(csv_path) and os.access(csv_path, os.W_OK)):
            parent = os.path.dirname(csv_path)
            if not os.path.exists(parent):
                print(f"[DEBUG] Parent folder does not exist: {parent}")
            else:
                print("[WARNING] File not found. Directory contents:")
                print(" -", "\n - ".join(os.listdir(parent)))
            QMessageBox.warning(None, "File Locked", 
                f"The file '{csv_path}' is not accessible.\n\nPlease close any programs or File Explorer windows that may be using it, then try again.")
            return

        # Flush to file just in case
        try:
            df.to_csv(csv_path, index=False)
            print("[DEBUG] Flushed file with to_csv before rename.")
        except Exception as e:
            print(f"[DEBUG] Could not flush file before rename: {e}")

        # Step 1: Rename file on disk FIRST
        if os.path.exists(unflagged_path):
            try:
                os.remove(unflagged_path)
                print(f"[CLEANUP] Removed existing file at {unflagged_path}")
            except Exception as e:
                print(f"[ERROR] Could not remove existing file at {unflagged_path}: {e}")
                return

        try:
            for attempt in range(3):
                try:
                    os.rename(csv_path, unflagged_path)
                    print(f"[RENAME SUCCESS] File renamed to: {unflagged_path}")
                    break
                except Exception as e:
                    print(f"[RENAME ATTEMPT {attempt+1}/3] Failed: {e}")
                    time.sleep(0.3)
            else:
                QMessageBox.warning(None, "File Locked", f"The file '{csv_path}' could not be renamed after retries.")
                return
        except Exception as e:
            print(f"[RENAME ERROR] Failed to rename file: {e}")
            return

        # Step 2: Update metadata
        fees = metadata.get("fees", {})
        if old_basename in fees:
            fees[new_basename] = fees.pop(old_basename)
        if "flagged_files" in metadata and old_basename in metadata["flagged_files"]:
            metadata["flagged_files"].remove(old_basename)
        metadata["flagged"] = bool(metadata.get("flagged_files"))

        # Step 3: Propagate in state/UI
        propagate_file_rename(csv_path, unflagged_path, state, stack)
        state["signals"].sessionsChanged.emit()
        state["signals"].dataChanged.emit()

        # Refresh dropdown
        if hasattr(stack.widget(2), "refresh_file_dropdown"):
            stack.widget(2).refresh_file_dropdown()
        # Step 4: Rename session folder if needed
        if "-flag" in original_session and not metadata["flagged"]:
            new_session_path = original_session.replace("-flag", "")
            if os.path.exists(original_session) and not os.path.exists(new_session_path):
                try:
                    if not os.access(original_session, os.W_OK):
                        QMessageBox.warning(None, "Folder Locked",
                            f"The folder '{original_session}' is not accessible.\n\nPlease close any programs or File Explorer windows that may be using it, then try again.")
                        return
                    os.rename(original_session, new_session_path)
                    print(f"[SESSION RENAME] Folder: {original_session} → {new_session_path}")
                    state["current_session"] = new_session_path
                    # Update all state paths
                    state["csv_paths"] = [p.replace(original_session, new_session_path) for p in state["csv_paths"]]
                    state["dataframes"] = {
                        p.replace(original_session, new_session_path): df
                        for p, df in state["dataframes"].items()
                    }
                    state["status_counts"] = {
                        os.path.basename(p.replace(original_session, new_session_path)): val
                        for p, val in state["status_counts"].items()
                    }
                    state["fee_schedule"] = {
                        os.path.basename(p.replace(original_session, new_session_path)): price
                        for p, price in state["fee_schedule"].items()
                    }

                    session_path = new_session_path
                    meta_path = os.path.join(session_path, "metadata", "metadata.json")
                except Exception as e:
                    print("[ERROR] Failed to rename session folder:", e)

        # Step 5: Save updated metadata
        try:
            os.makedirs(os.path.dirname(meta_path), exist_ok=True)
            write_metadata(meta_path, metadata)

            print(f"[METADATA] Saved. flagged={metadata.get('flagged')}, flagged_files={metadata.get('flagged_files', [])}")
        except Exception as e:
            print("[ERROR] Failed to write updated metadata:", e)

        # Final signal/UI updates
        if callable(state.get("refresh_current_session_label")):
            state["refresh_current_session_label"]()
        state["signals"].sessionsChanged.emit()
        state["signals"].dataChanged.emit()

    def update_other_display():
        content = ""
        has_other = False
        for fname, df in zip(session_csvs, dataframes):
            others = df[df["current_status"] == "other"]["Name"].tolist()
            if others:
                has_other = True
                content += f"{fname}:\n"
                for name in others:
                    content += f"  {name}\n"
        other_display.setText(content.strip())
        next_btn.setEnabled(not has_other)
        return has_other

    def update_status_counts():
        counts_per_file = {}
        for fname, df in zip(session_csvs, dataframes):
            counts = df["current_status"].value_counts().to_dict()
            counts_per_file[fname] = counts
        state["status_counts"] = counts_per_file

        # Populate status_table
        statuses = STATUS_LIST

        row_count = len(counts_per_file)
        status_table.setRowCount(row_count + 1)  # +1 for totals
        for i in range(row_count + 1):
            status_table.setRowHeight(i, 50)  # 🔥 Adjust this value as needed (e.g., 40 for extra padding)

        status_table.setColumnCount(len(statuses))
        status_table.setHorizontalHeaderLabels([s.capitalize() for s in statuses])
        status_table.setVerticalHeaderLabels(list(counts_per_file.keys()) + ["Total"])

        # Fill data rows
        totals = {status: 0 for status in statuses}
        for row_idx, (fname, counts) in enumerate(counts_per_file.items()):
            for col_idx, status in enumerate(statuses):
                val = counts.get(status, 0)
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_table.setItem(row_idx, col_idx, item)
                totals[status] += val

        # Fill totals row
        for col_idx, status in enumerate(statuses):
            total_val = totals[status]
            item = QTableWidgetItem(str(total_val))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_table.setItem(row_count, col_idx, item)

        status_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def update_person_buttons(df_index):
    # Fully replace scroll content with new widget + layout

        new_scroll_content, new_scroll_layout = make_scroll_content()

        new_scroll_content.setMinimumWidth(760)
        new_scroll_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        scroll.setWidget(new_scroll_content)



        state["_scroll_content"] = new_scroll_content
        state["_scroll_layout"] = new_scroll_layout

        selected_file = file_dropdown.currentText()

        def make_status_buttons(row, handler_fn):
            button_row = QHBoxLayout()
            button_group = QButtonGroup(screen)
            button_group.setExclusive(True)
            for status in STATUS_LIST:
                btn = QPushButton(status.replace("_", " ").capitalize())
                btn.setFixedWidth(110)
                btn.setFixedHeight(32)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.setCheckable(True)
                if row["current_status"] == status:
                    btn.setChecked(True)
                btn.clicked.connect(handler_fn(status))
                button_group.addButton(btn)
                button_row.addWidget(btn)
            wrapper = QWidget()
            wrapper.setLayout(button_row)
            wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            wrapper.setMinimumWidth(600)
            return wrapper

        if selected_file == "View All":
            grouped_rows = defaultdict(list)
            for path in state["csv_paths"]:
                df = state["dataframes"][path].copy()
                basename = os.path.basename(path)
                df["__source_file__"] = basename
                grouped_rows[basename].extend(df.to_dict("records"))

            for fname in sorted(grouped_rows):
                new_scroll_layout.addWidget(QLabel(f"======== {fname} ========"))
                for row in grouped_rows[fname]:
                    person_box = QVBoxLayout()
                    person_box.addWidget(QLabel(f"{row['Name']} — Default: {row['default_status']}"))
                    def handler_fn(status, person=row):
                        def handler():
                            for path in state["csv_paths"]:
                                df = state["dataframes"][path]
                                match = df[(df["Name"] == person["Name"]) & (df["Email"] == person["Email"])]

                                if not match.empty:
                                    df.at[match.index[0], "current_status"] = status
                                    update_other_display()
                                    update_status_counts()
                                    update_flag_state_for_file(path, state, stack)
                                    state["signals"].dataChanged.emit()
                                    break
                        return handler
                    person_box.addWidget(make_status_buttons(row, handler_fn))
                    wrapper = QFrame()
                    wrapper.setLayout(person_box)
                    wrapper.setFrameShape(QFrame.Shape.StyledPanel)  # ✅ add this
                    wrapper.setContentsMargins(12, 8, 12, 8)
                    wrapper.setMinimumWidth(760)
                    wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

                    new_scroll_layout.addWidget(wrapper)

            update_status_counts()
            return

        # --- Single file view ---
        if df_index == 0 or df_index > len(dataframes):
            print(f"[WARNING] Invalid df_index={df_index}")
            return

        try:
            path = state["csv_paths"][df_index - 1]
            df = state["dataframes"][path]
        except Exception as e:
            print(f"[ERROR] {e}")
            return

        for idx, row in df.iterrows():
            person_box = QVBoxLayout()
            person_box.addWidget(QLabel(f"{row['Name']} — Default: {row['default_status']}"))
            def handler_fn(status, row_idx=idx, df=df):
                def handler():
                    df.at[row_idx, "current_status"] = status
                    df.to_csv(path, index=False)
                    update_other_display()
                    update_status_counts()
                    update_flag_state_for_file(path, state, stack)
                    state["signals"].dataChanged.emit()
                return handler
            person_box.addWidget(make_status_buttons(row, handler_fn))
            wrapper = QFrame()
            wrapper.setLayout(person_box)
            wrapper.setFrameShape(QFrame.Shape.StyledPanel)
            wrapper.setContentsMargins(12, 8, 12, 8)
            wrapper.setMinimumWidth(760)
            wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            new_scroll_layout.addWidget(wrapper)
            new_scroll_layout.addSpacing(4)  # Or 8 for more room


        update_status_counts()

    def save_all_dataframes():
        for i, path in enumerate(state["csv_paths"]):
            df = state["dataframes"].get(path)
            if df is None:
                print(f"[WARNING] No DataFrame found for path: {path}")
                continue

            folder = os.path.dirname(path)
            try:
                os.makedirs(folder, exist_ok=True)
                df.to_csv(path, index=False)
                print(f"[SAVED] {path} with statuses:\n{df[['Name', 'current_status']]}")

            except OSError as e:
                if "non-existent directory" in str(e) and "-flag" in folder:
                    unflagged_folder = folder.replace("-flag", "")
                    new_path = os.path.join(unflagged_folder, os.path.basename(path))
                    os.makedirs(unflagged_folder, exist_ok=True)
                    df.to_csv(new_path, index=False)

                    # Remove old flagged file to prevent duplication
                    if os.path.exists(path):
                        os.remove(path)

                    # Update the path in state
                    state["csv_paths"][i] = new_path
                    state["dataframes"][new_path] = df
                    del state["dataframes"][path]
                else:
                    raise

    file_dropdown.addItem("View All")
    file_dropdown.addItems(session_csvs)
    file_dropdown.currentIndexChanged.connect(update_person_buttons)
    if dataframes:
        update_person_buttons(0)
        update_other_display()

    def go_to_fee_schedule():
        save_all_dataframes()
        fee_screen = create_fee_schedule_screen(stack, state)
        stack.removeWidget(stack.widget(3))
        stack.insertWidget(3, fee_screen)
        stack.setCurrentIndex(3)

    next_btn.clicked.connect(go_to_fee_schedule)
    left_container = QWidget()
    left_container.setLayout(left_layout)
    left_container.setMinimumWidth(800)
    left_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


    right_container = QWidget()
    right_container.setLayout(right_layout)



    main_layout.addWidget(left_container, stretch=1)
    main_layout.addWidget(right_container, stretch=2)




    def refresh_file_dropdown():
        populate_file_dropdown(file_dropdown, state, session_csvs, dataframes)

        update_other_display()

        # Force rerender for View All mode
        current_text = file_dropdown.currentText()
        if current_text == "View All":
            file_dropdown.setCurrentText("View All")
            update_person_buttons(0)

    screen.refresh_file_dropdown = refresh_file_dropdown
    next_btn.setEnabled(False)  # default state until verified
    update_other_display()      # initial evaluation

    return screen

#This is the fourth screen that the user sees
def create_fee_schedule_screen(stack, state) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)

    layout.addWidget(QLabel("Fee Schedule"))

    fee_inputs: Dict[str, QLineEdit] = {}
    state["fee_schedule"] = {}

    validator = QDoubleValidator(0.0, 10000.0, 2)
    validator.setNotation(QDoubleValidator.Notation.StandardNotation)

    csv_paths = state.get("csv_paths", [])
    saved_prices = {}
    nav_row = QHBoxLayout()

    def save_and_go_back():
        save_fee_schedule()
        stack.setCurrentIndex(2)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(save_and_go_back)
    nav_row.addWidget(back_btn)

    next_btn = QPushButton("Next")
    next_btn.setEnabled(False)
    def save_and_continue():
        for fname, inp in fee_inputs.items():
            try:
                value = float(inp.text())
                if value < 0:
                    raise ValueError
                state["fee_schedule"][fname] = round(value, 2)
            except ValueError:
                QMessageBox.warning(screen, "Invalid Fee", f"Invalid fee for {fname}. Please enter a non-negative number.")
                return

        # Update metadata again before going forward
        save_fee_schedule()

        summary_screen = create_payment_summary_screen(stack, state)
        stack.removeWidget(stack.widget(4))
        stack.insertWidget(4, summary_screen)
        stack.setCurrentIndex(4)

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
    layout.addLayout(file_form)
    def update_next_button_state():
        all_valid = True
        for inp in fee_inputs.values():
            text = inp.text().strip()
            try:
                value = float(text)
                if value < 0:
                    all_valid = False
                    break
            except ValueError:
                all_valid = False
                break
        next_btn.setEnabled(all_valid)

    if not csv_paths:
        layout.addWidget(QLabel("⚠️ No CSV files found for this session."))
    else:
        for path in csv_paths:
            fname = os.path.basename(path)
            inp = QLineEdit()
            inp.setValidator(validator)
            inp.setPlaceholderText("Enter cost")
            if fname in saved_prices:
                inp.setText(f"{float(saved_prices[fname]):.2f}")
            else:
                inp.setText("10.00")

            file_form.addRow(QLabel(fname), inp)
            fee_inputs[fname] = inp
            inp.textChanged.connect(update_next_button_state)
        update_next_button_state()

            

    layout.addWidget(QLabel("Bulk Assign to All:"))
    bulk_input = QLineEdit()
    bulk_input.setValidator(validator)
    bulk_input.setPlaceholderText("Enter fee to apply to all")
    layout.addWidget(bulk_input)

    # --- Logic to enable/disable Next button ---

    def save_fee_schedule():
        if not session_dir:
            QMessageBox.warning(screen, "No Session", "No active session to save fees to.")
            return

        metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
        if not os.path.exists(metadata_path):
            QMessageBox.warning(screen, "Missing Metadata", "Metadata file not found in current session.")
            return

        # Load metadata to check if session is paid
        try:
            with open(metadata_path, "r") as f:
                meta = json.load(f)
        except Exception as e:
            QMessageBox.critical(screen, "Error", f"Could not read metadata:\n{e}")
            return

        prices = {}
        for fname, inp in fee_inputs.items():
            text = inp.text()
            try:
                value = float(text)
                if value < 0:  # Matches new rule: values must be >= 1
                    raise ValueError
                prices[fname] = round(value, 2)
                state["fee_schedule"][fname] = round(value, 2)
            except ValueError:
                QMessageBox.warning(screen, "Invalid Fee", f"Invalid fee for {fname}. Please enter a number >= 0.")
                return

        try:
            # Calculate net_to_club using current pricing
            total_net = 0.0
            for path in state.get("csv_paths", []):
                fname = os.path.basename(path)
                price = prices.get(fname, 0)
                df = state["dataframes"].get(path)
                if df is None:
                    continue

                regular = (df["current_status"] == "regular").sum()
                manual  = (df["current_status"] == "manual").sum()

                gross = (regular + manual) * price
                tih_cut = gross * 0.10

                paypal = 0.0
                for _ in range(regular):
                    if price <= 10:
                        paypal += price * 0.05 + 0.09
                    else:
                        paypal += price * 0.0349 + 0.49

                net = gross - tih_cut - paypal
                total_net += net

            meta["fees"] = prices
            meta["net_to_club"] = round(total_net, 2)

            with open(metadata_path, "w") as f:
                json.dump(meta, f, indent=4)

            QMessageBox.information(screen, "Saved", "Fee schedule and net-to-club saved to metadata.")
            state["signals"].sessionsChanged.emit()

        except Exception as e:
            QMessageBox.critical(screen, "Error", f"Failed to save fees:\n{e}")

        state["signals"].dataChanged.emit()

    def assign_all():
        val = bulk_input.text().strip()
        if not val:
            return

        confirm = QMessageBox.question(
            screen,
            "Confirm Bulk Assign",
            f"This will set all file fees to ${val}. Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        for field in fee_inputs.values():
            field.setText(f"{float(val):.2f}")
        save_fee_schedule()
        update_next_button_state()


    """
    def reset_all():
        bulk_input.clear()
        for field in fee_inputs.values():
            field.setText("10.00")
        state["fee_schedule"] = {fname: 10.00 for fname in fee_inputs}
        save_fee_schedule()
        update_next_button_state()
    """

    assign_all_btn = QPushButton("Assign All")
    assign_all_btn.clicked.connect(assign_all)
    layout.addWidget(assign_all_btn)

    """ 
    reset_all_btn = QPushButton("Reset All")
    reset_all_btn.clicked.connect(reset_all)
    layout.addWidget(reset_all_btn)
 

    save_btn = QPushButton("Save Fee Schedule")
    save_btn.clicked.connect(save_fee_schedule)
    layout.addWidget(save_btn)
    """

    # Navigation
    
    next_btn.clicked.connect(save_and_continue)
    nav_row.addWidget(next_btn)

    layout.addLayout(nav_row)

    # Refresh method (if used elsewhere)
    def refresh_file_dropdown():
        nonlocal file_form, fee_inputs
        file_form = QFormLayout()
        file_basenames = [os.path.basename(p) for p in state.get("csv_paths", [])]
        fee_inputs.clear()
        for fname in file_basenames:
            inp = QLineEdit()
            inp.setValidator(validator)
            inp.setPlaceholderText("Enter cost")
            saved_price = state.get("fee_schedule", {}).get(fname)
            if saved_price is not None:
                inp.setText(f"{float(saved_price):.2f}")
            file_form.addRow(QLabel(fname), inp)
            fee_inputs[fname] = inp
        update_next_button_state()

    layout.addStretch()  # optional but nice

    screen.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    screen.refresh_file_dropdown = refresh_file_dropdown
    return screen

def create_payment_summary_screen(stack, state) -> QWidget:
    screen = QWidget()
    layout = QVBoxLayout(screen)
    mode = state.get("payment_summary_mode", "sorted")


    # Top row: Mark as Unpaid | Payment Summary | Mark as Paid
    top_row = QHBoxLayout()

    #unpaid_btn = QPushButton("Mark as Unpaid")
    paid_btn = QPushButton("Mark as Paid")
    header = QLabel("Payment Summary")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)

    #top_row.addWidget(unpaid_btn, alignment=Qt.AlignmentFlag.AlignLeft)
    #top_row.addStretch()
    top_row.addWidget(header, alignment=Qt.AlignmentFlag.AlignCenter)
    top_row.addStretch()
    top_row.addWidget(paid_btn, alignment=Qt.AlignmentFlag.AlignRight)

    layout.addLayout(top_row)
        # --- View Toggle Radio Buttons ---
    toggle_box = QGroupBox("View Mode")
    toggle_layout = QHBoxLayout()
    sorted_btn = QRadioButton("Sorted")
    unsorted_btn = QRadioButton("Unsorted")
    if mode == "unsorted":
        unsorted_btn.setChecked(True)
    else:
        sorted_btn.setChecked(True)


    def on_mode_changed():
        mode = "sorted" if sorted_btn.isChecked() else "unsorted"
        state["payment_summary_mode"] = mode
        build_payment_summary(mode)





    sorted_btn.toggled.connect(on_mode_changed)
    unsorted_btn.toggled.connect(on_mode_changed)

    toggle_layout.addWidget(sorted_btn)
    toggle_layout.addWidget(unsorted_btn)
    toggle_box.setLayout(toggle_layout)
    layout.addWidget(toggle_box)

    # Container layout to be refreshable
    summary_container_widget = QWidget()
    summary_container = QVBoxLayout(summary_container_widget)
    layout.addWidget(summary_container_widget)

    def build_payment_summary(mode="sorted"):
        def clear_layout(layout: QLayout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    clear_layout(item.layout())
                    item.layout().deleteLater()

        clear_layout(summary_container)

        session_dir = state.get("current_session")
        club_name = "Club"
        if session_dir:
            metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                    club_name = metadata.get("club", "Club")
                except:
                    pass

        statuses_to_show = STATUS_LIST[:-1]
        status_counts = state.get("status_counts", {})
        fee_schedule = state.get("fee_schedule", {})
        columns = ["Gross", "TrackitHub", "PayPal", club_name]

        grand_status_totals = dict.fromkeys(statuses_to_show, 0)
        grand_financial_totals = dict.fromkeys(columns, 0.0)

        if mode == "unsorted":
            all_files = sorted(status_counts.keys())
            grouped = {"All Files": all_files}
        else:
            grouped = {}
            for fname in status_counts:
                price = fee_schedule.get(fname, 0.0)
                grouped.setdefault(price, []).append(fname)

        financial_label_shown = False  # ✅ track if we've added the label

        for group_key in (sorted(grouped) if mode == "sorted" else grouped):
            files = sorted(grouped[group_key])
            price = group_key if mode == "sorted" else None
            label_text = f"======== ${price:.2f} ========" if mode == "sorted" else "======== All Files ========"
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold; padding: 6px;")

            row_layout = QHBoxLayout()
            left_col = QVBoxLayout()
            left_col.addWidget(label)

            show_total = len(files) > 1

            # Status Table
            status_table = QTableWidget()
            status_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            status_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            status_table.setColumnCount(len(statuses_to_show))
            status_table.setRowCount(len(files) + (1 if show_total else 0))
            status_table.setHorizontalHeaderLabels([s.capitalize() for s in statuses_to_show])
            status_table.setVerticalHeaderLabels(files + (["Total"] if show_total else []))
            status_totals = dict.fromkeys(statuses_to_show, 0)

            for row_idx, fname in enumerate(files):
                counts = status_counts.get(fname, {})
                for col_idx, status in enumerate(statuses_to_show):
                    count = int(counts.get(status, 0))
                    item = QTableWidgetItem(str(count))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_table.setItem(row_idx, col_idx, item)
                    status_totals[status] += count
                    grand_status_totals[status] += count

            if show_total:
                for col_idx, status in enumerate(statuses_to_show):
                    item = QTableWidgetItem(str(status_totals[status]))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    status_table.setItem(len(files), col_idx, item)

            status_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            left_col.addWidget(status_table)

            # Financial Table
            right_col = QVBoxLayout()
            if not financial_label_shown:
                right_col.addWidget(QLabel("Financial Summary"))
                financial_label_shown = True

            financial_table = QTableWidget()
            financial_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            financial_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            financial_table.setColumnCount(len(columns))
            financial_table.setRowCount(len(files) + (1 if show_total else 0))
            financial_table.setHorizontalHeaderLabels(columns)
            financial_table.setVerticalHeaderLabels(files + (["Total"] if show_total else []))
            financial_totals = dict.fromkeys(columns, 0.0)

            for row_idx, fname in enumerate(files):
                price = fee_schedule.get(fname, 0.0)
                counts = status_counts.get(fname, {})
                regular = counts.get("regular", 0)
                manual = counts.get("manual", 0)

                gross = (regular + manual) * price
                trackithub = gross * 0.10
                paypal = sum(
                    price * 0.05 + 0.09 if price <= 10 else price * 0.0349 + 0.49
                    for _ in range(regular)
                )
                net = gross - trackithub - paypal
                vals = [gross, trackithub, paypal, net]

                for col_idx, val in enumerate(vals):
                    item = QTableWidgetItem(f"${val:.2f}")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    financial_table.setItem(row_idx, col_idx, item)
                    financial_totals[columns[col_idx]] += val
                    grand_financial_totals[columns[col_idx]] += val

            if show_total:
                for col_idx, col in enumerate(columns):
                    item = QTableWidgetItem(f"${financial_totals[col]:.2f}")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    financial_table.setItem(len(files), col_idx, item)

            financial_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            right_col.addWidget(financial_table)

            row_layout.addLayout(left_col, 2)
            row_layout.addLayout(right_col, 2)
            summary_container.addLayout(row_layout)

        # Grand Totals Section
        if mode == "sorted":
            row_layout = QHBoxLayout()
            left_col = QVBoxLayout()

            status_table = QTableWidget(1, len(statuses_to_show))
            status_table.setHorizontalHeaderLabels([s.capitalize() for s in statuses_to_show])
            for col_idx, status in enumerate(statuses_to_show):
                val = grand_status_totals[status]
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                status_table.setItem(0, col_idx, item)
            status_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            left_col.addWidget(status_table)

            right_col = QVBoxLayout()
            financial_table = QTableWidget(1, len(columns))
            financial_table.setHorizontalHeaderLabels(columns)
            for col_idx, col in enumerate(columns):
                val = grand_financial_totals[col]
                item = QTableWidgetItem(f"${val:.2f}")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                financial_table.setItem(0, col_idx, item)
            financial_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            right_col.addWidget(financial_table)

            row_layout.addLayout(left_col, 2)
            row_layout.addLayout(right_col, 2)
            summary_container.addLayout(row_layout)

        
    build_payment_summary(mode)

    def update_paid_status(status: bool):
        session_dir = state.get("current_session")
        if not session_dir:
            QMessageBox.warning(screen, "No Session", "No active session loaded.")
            return

        meta_path = os.path.join(session_dir, "metadata", "metadata.json")
        if not os.path.exists(meta_path):
            QMessageBox.warning(screen, "Missing Metadata", "Metadata file not found in current session.")
            return

        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)
            metadata["paid"] = status
            write_metadata(meta_path, metadata)
            QMessageBox.information(screen, "Updated", f"Session marked as {'paid' if status else 'unpaid'}.")
            state["signals"].sessionsChanged.emit()
        except Exception as e:
            QMessageBox.critical(screen, "Error", f"Failed to update paid status:\n{e}")

    def on_mark_paid():
        update_paid_status(True)
        state["tabs"].setCurrentIndex(2)  # 0=Program, 1=Current Session Files, 2=All Sessions

    paid_btn.clicked.connect(on_mark_paid)

    #unpaid_btn.clicked.connect(lambda: update_paid_status(False))

    def refresh_summary():
        new_screen = create_payment_summary_screen(stack, state)
        stack.removeWidget(stack.widget(4))
        stack.insertWidget(4, new_screen)
        stack.setCurrentIndex(4)

    screen.refresh_summary = refresh_summary

    nav_row = QHBoxLayout()
    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(3))
    nav_row.addWidget(back_btn)
    layout.addLayout(nav_row)

    return screen

# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------

def create_program_flow_tab(state: Dict, stack:QStackedWidget) -> QStackedWidget:
    stack = QStackedWidget()
    state["stack"] = stack

    stack.addWidget(create_welcome_screen(stack, state))             # 0
    stack.addWidget(create_session_creation_screen(stack, state))    # 1
    stack.addWidget(create_assign_status_screen(stack, state))       # 2
    stack.addWidget(QWidget())  # Placeholder for fee screen          # 3
    stack.addWidget(QWidget())  # Placeholder for payment summary     # 4

    return stack

def create_all_sessions_tab(state: dict) -> QWidget:
    class AllSessionsTabSignals(QObject):
        fileDoubleClicked = pyqtSignal(str)

    all_signals = AllSessionsTabSignals()
    state["all_sessions_tab_signals"] = all_signals

    scr = QWidget()
    layout = QVBoxLayout(scr)

    # --- Header Row with Filters ---
    header_row = QHBoxLayout()
    header = QLabel("All Sessions Overview")
    header.setAlignment(Qt.AlignmentFlag.AlignLeft)
    header_row.addWidget(header)

    # Flagged/Unflagged Radio Group
    flag_group = QButtonGroup(scr)
    flagged_radio = QRadioButton("Flagged")
    unflagged_radio = QRadioButton("Unflagged")
    dummy_flag_radio = QRadioButton()
    dummy_flag_radio.hide()
    flag_group.setExclusive(True)
    flag_group.addButton(flagged_radio)
    flag_group.addButton(unflagged_radio)
    flag_group.addButton(dummy_flag_radio)

    # Paid/Unpaid Radio Group
    pay_group = QButtonGroup(scr)
    paid_radio = QRadioButton("Paid")
    unpaid_radio = QRadioButton("Unpaid")
    dummy_pay_radio = QRadioButton()
    dummy_pay_radio.hide()
    pay_group.setExclusive(True)
    pay_group.addButton(paid_radio)
    pay_group.addButton(unpaid_radio)
    pay_group.addButton(dummy_pay_radio)

    # Reset Menu Button
    reset_menu_btn = QToolButton()
    reset_menu_btn.setText("Reset Filters ▼")
    reset_menu = QMenu()
    reset_menu.addAction("Clear All", lambda: clear_all_filters())
    reset_menu.addAction("Clear Flagged/Unflagged", lambda: clear_filter_group(flag_group, dummy_flag_radio))
    reset_menu.addAction("Clear Paid/Unpaid", lambda: clear_filter_group(pay_group, dummy_pay_radio))
    reset_menu_btn.setMenu(reset_menu)
    reset_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    # Add to layout
    header_row.addWidget(flagged_radio)
    header_row.addWidget(unflagged_radio)
    header_row.addSpacing(12)
    header_row.addWidget(paid_radio)
    header_row.addWidget(unpaid_radio)
    header_row.addSpacing(12)
    header_row.addWidget(reset_menu_btn)
    header_row.addStretch()
    layout.addLayout(header_row)

    # Ensure dummy buttons persist
    layout.addWidget(dummy_flag_radio)
    layout.addWidget(dummy_pay_radio)

    # Tree
    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # Tree (top half)
    tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
    splitter.addWidget(tree)

    # Edit Box (bottom half)
    edit_box = QGroupBox("Edit Player Notes")
    edit_layout = QFormLayout(edit_box)
    edit_layout.setVerticalSpacing(12)  # Or 10, tweak as needed
    edit_layout.setLabelAlignment(Qt.AlignmentFlag.AlignTop)

    selected_file_label = QLabel("Selected file: None")
    edit_layout.addRow(selected_file_label)
    name_dropdown = QComboBox()
    name_dropdown.setMinimumHeight(50)
    name_dropdown.setEditable(True)
    name_dropdown.lineEdit().setReadOnly(True)


    abnote_input = QLineEdit()
    save_btn = QPushButton("Save Note")
    select_label = QLabel("Select Name:")
    select_label.setAlignment(Qt.AlignmentFlag.AlignTop)
    edit_layout.addRow(select_label, name_dropdown)

    note_label = QLabel("Player Note:")
    note_label.setAlignment(Qt.AlignmentFlag.AlignTop)
    edit_layout.addRow(note_label, abnote_input)

    edit_layout.addWidget(save_btn)
    edit_box.setEnabled(False)
    splitter.addWidget(edit_box)
    splitter.setSizes([200,250])
    name_dropdown.setFixedSize(600, 60)
    abnote_input.setFixedSize(600, 400)









    # Adjust default height proportions
    splitter.setStretchFactor(0, 1)  # Tree
    splitter.setStretchFactor(1, 3)  # Edit box (more space)

    layout.addWidget(splitter)

    
    
    edit_box.setEnabled(False)

    selected_session = None
    selected_file = None
    df = None

    def refresh_all_sessions():
        tree.clear()
        sessions_path = SESSIONS_DIR
        if not os.path.exists(sessions_path):
            return

        sessions = []
        for session_name in os.listdir(sessions_path):
            session_path = os.path.join(sessions_path, session_name)
            metadata_path = os.path.join(session_path, "metadata", "metadata.json")
            if not os.path.exists(metadata_path):
                continue
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                last_opened_str = metadata.get("last_opened", "1970-01-01T00:00:00")
                last_opened = datetime.fromisoformat(last_opened_str)
                sessions.append((session_name, session_path, metadata, last_opened))
            except:
                continue

        sessions.sort(key=lambda x: x[3], reverse=True)

        # Apply filters
        show_flagged = flagged_radio.isChecked()
        show_unflagged = unflagged_radio.isChecked()
        show_paid = paid_radio.isChecked()
        show_unpaid = unpaid_radio.isChecked()

        for session_name, session_path, metadata, _ in sessions:
            is_flagged = "-flag" in session_name
            is_paid = metadata.get("paid", False)

            if show_flagged and not is_flagged:
                continue
            if show_unflagged and is_flagged:
                continue
            if show_paid and not is_paid:
                continue
            if show_unpaid and is_paid:
                continue

            status_str = "paid ✅" if is_paid else "unpaid ❌"
            net = metadata.get("net_to_club", None)
            formatted_total = f"${net:.2f}" if isinstance(net, (int, float)) else "No total yet"
            display_name = f"{session_name} — {status_str} — total {formatted_total}"

            parent_item = QTreeWidgetItem([display_name])
            csv_path = os.path.join(session_path, "csv")
            if not os.path.exists(csv_path):
                continue
            for fname in sorted(os.listdir(csv_path)):
                if fname.endswith(".csv"):
                    file_item = QTreeWidgetItem(parent_item, [fname])
                    full_path = os.path.join(csv_path, fname)
                    file_item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            tree.addTopLevelItem(parent_item)

    def on_tree_item_selected(item, _prev=None):
        nonlocal selected_session, selected_file, df
        if item is None:
            return
        parent = item.parent()
        if parent is None:
            return
        selected_session = parent.text(0).split(" — ")[0]
        selected_file = item.text(0)
        selected_file_label.setText(f"Selected file: {selected_file}")

        session_dir = os.path.join(SESSIONS_DIR, selected_session)
        full_path = os.path.join(session_dir, "csv", selected_file)
        if not os.path.exists(full_path):
            return
        try:
            df = pd.read_csv(full_path)
            if "AnkleBreaker notes" not in df.columns:
                df["AnkleBreaker notes"] = ""
            if "Name" in df.columns:
                name_dropdown.blockSignals(True)
                name_dropdown.clear()
                name_dropdown.addItems(df["Name"].dropna().astype(str).tolist())
                name_dropdown.blockSignals(False)
                if not df["Name"].empty:
                    name_dropdown.setCurrentIndex(0)
                    on_name_selected(name_dropdown.currentText())
                edit_box.setEnabled(True)
        except Exception:
            df = None
            edit_box.setEnabled(False)

    def on_tree_item_double_clicked(item: QTreeWidgetItem, column: int):
        parent = item.parent()
        if parent is None:
            return
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path and os.path.exists(file_path):
            state["tabs"].setCurrentIndex(4)
            all_signals.fileDoubleClicked.emit(file_path)

    def on_name_selected(name):
        if df is None:
            return
        matches = df[df["Name"] == name]
        if matches.empty:
            abnote_input.clear()
            return
        abnote = matches["AnkleBreaker notes"].values[0] if "AnkleBreaker notes" in matches.columns else ""
        abnote_input.setText(str(abnote))

    def on_save_note():
        nonlocal selected_session, selected_file, df
        if df is None:
            return
        name = name_dropdown.currentText()
        if not name:
            return
        if "AnkleBreaker notes" not in df.columns:
            df["AnkleBreaker notes"] = ""
        df["AnkleBreaker notes"] = df["AnkleBreaker notes"].astype(str)
        df.loc[df["Name"] == name, "AnkleBreaker notes"] = abnote_input.text()
        df["default_status"] = df.apply(lambda row: determine_default_status(row["Notes"], row["Name"]), axis=1)

        session_path = os.path.join(SESSIONS_DIR, selected_session)
        csv_dir = os.path.join(session_path, "csv")
        file_path = os.path.join(csv_dir, selected_file)
        df.to_csv(file_path, index=False)

        state["signals"].sessionsChanged.emit()
        state["signals"].dataChanged.emit()
        refresh_all_sessions()

    def clear_filter_group(group: QButtonGroup, dummy: QRadioButton):
        dummy.setChecked(True)
        refresh_all_sessions()

    def clear_all_filters():
        clear_filter_group(flag_group, dummy_flag_radio)
        clear_filter_group(pay_group, dummy_pay_radio)

    # Signals
    flagged_radio.toggled.connect(refresh_all_sessions)
    unflagged_radio.toggled.connect(refresh_all_sessions)
    paid_radio.toggled.connect(refresh_all_sessions)
    unpaid_radio.toggled.connect(refresh_all_sessions)

    tree.itemClicked.connect(on_tree_item_selected)
    tree.currentItemChanged.connect(on_tree_item_selected)
    tree.itemDoubleClicked.connect(on_tree_item_double_clicked)
    name_dropdown.currentTextChanged.connect(on_name_selected)
    save_btn.clicked.connect(on_save_note)

    state["signals"].sessionsChanged.connect(refresh_all_sessions)
    refresh_all_sessions()

    scr.refresh = refresh_all_sessions
    scr.setSizePolicy(scr.sizePolicy().Policy.Expanding, scr.sizePolicy().Policy.Expanding)
    return scr

def create_current_session_files_tab(state: Dict) -> QWidget:
    scr = QWidget()
    scr_layout = QVBoxLayout(scr)
    state["_wheel_filter"] = state.get("_wheel_filter") or WheelEventFilter()
    state.setdefault("fee_schedule", {})

    header = QLabel("Files in Current Session")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    scr_layout.addWidget(header)

    file_dropdown = QComboBox()
    file_dropdown.installEventFilter(state["_wheel_filter"])
    scr_layout.addWidget(file_dropdown)

    table = QTableWidget()
    scr_layout.addWidget(table)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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

    def load_all_files_to_table():
        table.clear()
        table.setRowCount(0)
        table.setColumnCount(0)

        current_session = state.get("current_session")
        csv_dir = os.path.join(current_session, "csv")
        filenames = sorted(f for f in os.listdir(csv_dir) if f.endswith(".csv"))

        dfs = []
        color_map = {}
        colors = [QColor("lightblue"), QColor("lightgreen"), QColor("orange"), QColor("violet"), QColor("lightgray")]

        for i, fname in enumerate(filenames):
            full_path = os.path.join(csv_dir, fname)
            try:
                df = pd.read_csv(full_path)
                df["File"] = fname
                dfs.append(df)
                color_map[fname] = colors[i % len(colors)]
            except Exception:
                continue

        if not dfs:
            table.setColumnCount(1)
            table.setRowCount(1)
            table.setHorizontalHeaderLabels(["Error"])
            table.setItem(0, 0, QTableWidgetItem("Error loading any CSV files."))
            return

        combined_df = pd.concat(dfs, ignore_index=True)
        table.setColumnCount(len(combined_df.columns))
        table.setHorizontalHeaderLabels(combined_df.columns.tolist())
        table.setRowCount(len(combined_df))

        for i, row in combined_df.iterrows():
            row_file = row["File"]
            row_color = color_map.get(row_file, QColor("white"))
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(row_color)
                table.setItem(i, j, item)

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def refresh():
        file_dropdown.blockSignals(True)
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
        file_dropdown.addItem("View All")
        file_dropdown.addItems(filenames)

        def update_display(index):
            fname = file_dropdown.itemText(index)
            state["_last_selected_file"] = fname
            if fname == "View All":
                load_all_files_to_table()
            else:
                full_path = os.path.join(csv_dir, fname)
                load_csv_to_table(full_path)

        file_dropdown.currentIndexChanged.connect(update_display)

        # Try to re-select previously selected file or default
        previously_selected = state.get("_last_selected_file")
        options = ["View All"] + filenames
        if previously_selected in options:
            idx = options.index(previously_selected)
        else:
            idx = 0

        file_dropdown.setCurrentIndex(idx)
        update_display(idx)

        file_dropdown.blockSignals(False)

    state["signals"].dataChanged.connect(refresh)
    state["signals"].sessionsChanged.connect(refresh)

    scr.refresh = refresh
    scr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return scr

def create_any_file_viewer_tab(state: Dict) -> QWidget:
    scr = QWidget()
    scr.setObjectName("any_file_viewer_tab")
    layout = QVBoxLayout(scr)
    state["_wheel_filter"] = state.get("_wheel_filter") or WheelEventFilter()

    header = QLabel("Browse Any Session File")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    club_dropdown = QComboBox()
    club_dropdown.installEventFilter(state["_wheel_filter"])

    session_dropdown = QComboBox()
    session_dropdown.installEventFilter(state["_wheel_filter"])

    file_dropdown = QComboBox()
    file_dropdown.installEventFilter(state["_wheel_filter"])

    layout.addWidget(QLabel("Select Club:"))
    layout.addWidget(club_dropdown)
    layout.addWidget(QLabel("Select Session:"))
    layout.addWidget(session_dropdown)
    layout.addWidget(QLabel("Select File:"))
    layout.addWidget(file_dropdown)

    table = QTableWidget()
    layout.addWidget(table)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    club_session_file_map = {}

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

    def load_club_session_file_structure():
        structure = defaultdict(lambda: defaultdict(list))
        for session_name in os.listdir(SESSIONS_DIR):
            session_path = os.path.join(SESSIONS_DIR, session_name)
            if not os.path.isdir(session_path):
                continue
            try:
                # Extract club name from session folder name
                parts = session_name.split("-")
                if len(parts) < 3:
                    continue
                club = parts[1]
                csv_path = os.path.join(session_path, "csv")
                if not os.path.isdir(csv_path):
                    continue

                for fname in os.listdir(csv_path):
                    if fname.endswith(".csv"):
                        full_path = os.path.join(csv_path, fname)
                        if os.path.exists(full_path):
                            structure[club][session_name].append((session_path, fname))

            except Exception as e:
                continue
        return structure

    def refresh_dropdowns():
        nonlocal club_session_file_map

        club_session_file_map = load_club_session_file_structure()

        club_dropdown.blockSignals(True)
        session_dropdown.blockSignals(True)
        file_dropdown.blockSignals(True)

        club_dropdown.clear()
        session_dropdown.clear()
        file_dropdown.clear()
        table.setRowCount(0)
        table.setColumnCount(0)

        clubs = sorted(club_session_file_map.keys())
        club_dropdown.addItems(clubs)

        if clubs:
            club_dropdown.setCurrentIndex(0)
            on_club_change()

        club_dropdown.blockSignals(False)
        session_dropdown.blockSignals(False)
        file_dropdown.blockSignals(False)

    def on_club_change():
        session_dropdown.blockSignals(True)
        file_dropdown.blockSignals(True)

        session_dropdown.clear()
        file_dropdown.clear()
        table.setRowCount(0)
        table.setColumnCount(0)

        selected_club = club_dropdown.currentText()
        print(f"[UI] Selected club: {selected_club}")
        if selected_club in club_session_file_map:
            sessions = sorted(club_session_file_map[selected_club].keys())
            session_dropdown.addItems(sessions)
            if sessions:
                session_dropdown.setCurrentIndex(0)
                on_session_change()

        session_dropdown.blockSignals(False)
        file_dropdown.blockSignals(False)

    def on_session_change():
        file_dropdown.blockSignals(True)
        file_dropdown.clear()
        table.setRowCount(0)
        table.setColumnCount(0)

        selected_club = club_dropdown.currentText()
        selected_session = session_dropdown.currentText()
        print(f"[UI] Selected session: {selected_session}")
        if selected_club in club_session_file_map and selected_session in club_session_file_map[selected_club]:
            file_names = [f for (_, f) in club_session_file_map[selected_club][selected_session]]
            file_dropdown.addItems(file_names)
            if file_names:
                file_dropdown.setCurrentIndex(0)
                on_file_change()

        file_dropdown.blockSignals(False)

    def on_file_change():
        selected_club = club_dropdown.currentText()
        selected_session = session_dropdown.currentText()
        selected_file = file_dropdown.currentText()
        print(f"[UI] Selected file: {selected_file}")
        if not (selected_club and selected_session and selected_file):
            return
        for folder, fname in club_session_file_map[selected_club][selected_session]:
            if fname == selected_file:
                path = os.path.join(folder, "csv", fname)
                load_csv_to_table(path)
                break

    def load_file_from_path(file_path: str):
        path = Path(file_path)
        try:
            session_folder = path.parents[1]
            session_name = session_folder.name
            club = None

            meta_path = os.path.join(session_folder, "metadata", "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                    club = meta.get("club")

            if not club or club not in club_session_file_map:
                print(f"[WARN] Club not found: {club}")
                return
            if session_name not in club_session_file_map[club]:
                print(f"[WARN] Session not found: {session_name}")
                return
            file = path.name
            files = [f for (_, f) in club_session_file_map[club][session_name]]
            if file not in files:
                print(f"[WARN] File not found: {file}")
                return

            club_dropdown.blockSignals(True)
            session_dropdown.blockSignals(True)
            file_dropdown.blockSignals(True)

            club_dropdown.setCurrentText(club)
            on_club_change()
            session_dropdown.setCurrentText(session_name)
            on_session_change()
            file_dropdown.setCurrentText(file)
            on_file_change()

            club_dropdown.blockSignals(False)
            session_dropdown.blockSignals(False)
            file_dropdown.blockSignals(False)

        except Exception as e:
            print(f"[ERROR] Failed to load file from path: {e}")

    def connect_file_viewer_signals():
        flagged_signals = state.get("flagged_tab_signals")
        all_signals = state.get("all_sessions_tab_signals")
        if flagged_signals:
            flagged_signals.fileDoubleClicked.connect(load_file_from_path)
        if all_signals:
            all_signals.fileDoubleClicked.connect(load_file_from_path)

    # Hook up signals
    club_dropdown.currentTextChanged.connect(on_club_change)
    session_dropdown.currentTextChanged.connect(on_session_change)
    file_dropdown.currentTextChanged.connect(on_file_change)
    state["signals"].sessionsChanged.connect(refresh_dropdowns)

    # Add .refresh method for external trigger
    def refresh():
        refresh_dropdowns()
    scr.refresh = refresh

    # Initial setup
    refresh_dropdowns()
    connect_file_viewer_signals()

    scr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    return scr

# ---------------------------------------------------------------------
# Main window builder
# ---------------------------------------------------------------------
def load_session_from_folder(session_dir: str, stack: QStackedWidget, state: Dict, parent_widget: QWidget):
    metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
    csv_dir = os.path.join(session_dir, "csv")

    
    if not os.path.exists(metadata_path) or not os.path.isdir(csv_dir):
        QMessageBox.warning(parent_widget, "Invalid Session", "Selected folder does not appear to be a valid session.")
        return

    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Inline default status logic
        
        # Set session metadata
        state["current_session"] = session_dir
        for fn in state.get("_refresh_crud_banners", []):
            fn()

        state["csv_paths"] = []
        state["dataframes"] = {}
        state["status_counts"] = {}

        fee_schedule = metadata.get("fees", {})
        state["fee_schedule"] = {fname: float(val) for fname, val in fee_schedule.items() if isinstance(val, (int, float)) or str(val).replace(".", "", 1).isdigit()}

        filenames = [os.path.basename(p) for p in get_csv_paths_from_dir(csv_dir)]

        for fname in filenames:
            path = os.path.join(csv_dir, fname)
            try:
                # Force expected structure
                df = pd.read_csv(path)
    
                # Only apply header names if they’re not already correct
                expected_headers = ["Name", "Email", "Phone Number", "Status", "Registration Time", "Notes"]
                if list(df.columns[:6]) != expected_headers:
                    df.columns = expected_headers

                df["default_status"] = df.apply(lambda row: determine_default_status(row["Notes"], row["Name"]), axis=1)
                if "current_status" not in df.columns:
                    df["current_status"] = df["default_status"]

                df["AnkleBreaker notes"] = ""

                state["csv_paths"].append(path)
                state["dataframes"][path] = df

                counts = df["current_status"].value_counts().to_dict()
                state["status_counts"][fname] = counts

            except Exception as e:
                print(f"[ERROR] Failed to load CSV {path}: {e}")

        # Load and activate Assign Status screen
        new_assign_screen = create_assign_status_screen(stack, state)
        stack.removeWidget(stack.widget(2))
        stack.insertWidget(2, new_assign_screen)
        stack.setCurrentIndex(2)

    except Exception as e:
        QMessageBox.critical(parent_widget, "Load Failed", f"Could not load session:\n{e}")

def reset_session(stack: QStackedWidget, state: Dict, parent: QWidget):
    reply = QMessageBox.question(
        parent,
        "Confirm Reset",
        "Are you sure you want to reset the current session?\nThis cannot be undone.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    # Save all DataFrames, with fallback if folder was renamed due to unflagging
    for i, path in enumerate(state.get("csv_paths", [])):
        dataframes = state.get("dataframes", {})
        df = None
        if isinstance(dataframes, dict):
            df = dataframes.get(path)
        elif isinstance(dataframes, list):
            try:
                df = dataframes[i]
            except IndexError:
                continue
        if df is None:
            continue

        folder = os.path.dirname(path)
        try:
            os.makedirs(folder, exist_ok=True)
            df.to_csv(path, index=False)
        except OSError as e:
            if "non-existent directory" in str(e) and "-flag" in folder:
                unflagged_folder = folder.replace("-flag", "")
                new_path = os.path.join(unflagged_folder, os.path.basename(path))
                os.makedirs(unflagged_folder, exist_ok=True)
                df.to_csv(new_path, index=False)
                # Update the path in state to avoid future errors
                state["csv_paths"][i] = new_path
            else:
                raise

    # Clear session-related state
    keys_to_clear = [
        "csv_paths", "dataframes", "df", "current_session",
        "fee_schedule", "status_counts", "_last_selected_file"
    ]
    for key in keys_to_clear:
        state.pop(key, None)

    # ✅ Unlock file upload controls
    state["session_locked"] = False
    if state.get("_upload_files_btn"):
        state["_upload_files_btn"].setEnabled(True)
    if state.get("_upload_folder_btn"):
        state["_upload_folder_btn"].setEnabled(True)

    # Rebuild the stack from scratch
    if stack:
        stack.removeWidget(stack.widget(0))
        stack.removeWidget(stack.widget(1))
        stack.removeWidget(stack.widget(2))

        stack.insertWidget(0, create_welcome_screen(stack, state))
        stack.insertWidget(1, create_session_creation_screen(stack, state))
        stack.insertWidget(2, create_assign_status_screen(stack, state))
        stack.setCurrentIndex(0)

    # Refresh banners if needed
    for fn in state.get("_refresh_crud_banners", []):
        fn()
    state["signals"].sessionsChanged.emit()  # ✅ Add this here

    # Notify the user
    QMessageBox.information(parent, "Session Reset", "The session has been reset.")

def create_main_window() -> QWidget:
    container = QWidget()
    main_layout = QVBoxLayout(container)
    container.setContentsMargins(6, 6, 6, 6)      # ⬅️ Adds margin around the outer container
    main_layout.setContentsMargins(6, 6, 6, 6)    # ⬅️ Adds margin inside the layout itself
    main_layout.setSpacing(8)                         # ⬅️ Adds space between elements like top_bar and stack

    main_layout.setSpacing(0)

    state: Dict = {}
    state["signals"] = SignalBus()
    state["global_metadata"] = load_global_metadata()
    state["_refresh_crud_banners"] = []
    state["current_session"] = None
    state["session_created"] = False
    state["session_deleted"] = False

    # --- Top Button Bar (AnkleBar + Past Club Sessions + Session Label) ---
    top_bar = QHBoxLayout()
    top_bar.setContentsMargins(0, 0, 0, 6)

    anklebar_btn = QToolButton()
    anklebar_btn.setText("⚙️ AnkleBar")
    anklebar_btn.setMinimumHeight(40)


    anklebar_btn.setProperty("class", "menu-button")

    anklebar_menu = QMenu()
    anklebar_btn.setMenu(anklebar_menu)

    anklebar_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    anklebar_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    anklebar_btn.style().unpolish(anklebar_btn)
    anklebar_btn.style().polish(anklebar_btn)

    past_sessions_btn = QPushButton("📂 Past Club Sessions")
    past_sessions_btn.setMinimumHeight(40)
    past_sessions_btn.setProperty("class", "menu-button")
    past_sessions_btn.style().unpolish(past_sessions_btn)
    past_sessions_btn.style().polish(past_sessions_btn)

    session_label = QLabel()
    session_label.setObjectName("sessionStatusLabel")
    session_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    top_bar.addWidget(anklebar_btn)
    top_bar.addSpacing(12)  # optional small gap
    top_bar.addWidget(past_sessions_btn)
    top_bar.addWidget(session_label)
    top_bar.addStretch()

    main_layout.addLayout(top_bar)  # 🧷 Add to the same layout as the tabs

    def refresh_session_label():
        path = state.get("current_session")
        session_label.setText(f"Current Session: {os.path.basename(path)}" if path else "")

    state["refresh_current_session_label"] = refresh_session_label
    state["_refresh_crud_banners"].append(refresh_session_label)
    refresh_session_label()

    # ---------------- Menu Actions ----------------
    def open_folder_dialog():
        start_dir = str(SESSIONS_DIR) if os.path.exists(SESSIONS_DIR) else str(BASE_DIR)
        folder = QFileDialog.getExistingDirectory(container, "Select Session Folder", start_dir)
        if not folder:
            return
        folder_name = os.path.basename(folder)
        reply = QMessageBox.question(
            container, "Confirm Load",
            f"You are about to load session:\n\n📁 {folder_name}\n\nContinue?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Ok:
            load_session_from_folder(folder, state["stack"], state, container)

    def reset_session_wrapper():
        reset_session(state["stack"], state, container)

    def launch_graphical_loader():
        state["previous_screen_index"] = state["stack"].currentIndex()
        state["previous_tab_index"] = state["tabs"].currentIndex()
        state["previous_program_screen"] = state["stack"].currentIndex()
        graphical_screen = create_graphical_loader_screen(state["stack"], state)
        if state["stack"].indexOf(graphical_screen) == -1:
            state["stack"].addWidget(graphical_screen)
        state["tabs"].setCurrentIndex(0)
        state["stack"].setCurrentWidget(graphical_screen)
        past_sessions_btn.setEnabled(False)

    def choose_base_path_dialog():
        selected_dir = QFileDialog.getExistingDirectory(container, "Choose Where to Place AnkleBreakerData Folder")
        if not selected_dir:
            return

        try:
            new_base = Path(selected_dir) / "AnkleBreakerData"
            sessions_dir = new_base / "sessions"
            metadata_path = new_base / "metadata.json"

            # Create folders
            new_base.mkdir(parents=True, exist_ok=True)
            sessions_dir.mkdir(parents=True, exist_ok=True)

            # Create default metadata.json if missing
            if not metadata_path.exists():
                with open(metadata_path, "w") as f:
                    json.dump({"clubs": DEFAULT_CLUBS}, f, indent=4)

            # Update config and notify
            settings.setValue("base_path", str(new_base))
            QMessageBox.information(
                container,
                "Restart Required",
                f"✅ Created AnkleBreakerData at:\n{new_base}\n\nPlease restart the app to apply changes."
            )

        except Exception as e:
            QMessageBox.critical(
                container,
                "Folder Creation Failed",
                f"❌ Could not create required folders at:\n{new_base}\n\nError:\n{e}"
            )

    def delete_session_dialog():
        start_dir = str(SESSIONS_DIR) if os.path.exists(SESSIONS_DIR) else str(BASE_DIR)
        folder = QFileDialog.getExistingDirectory(container, "Select Session Folder to Delete", start_dir)
        if not folder:
            return
        session_name = os.path.basename(folder)
        reply = QMessageBox.question(
            container, "Confirm Delete",
            f"Are you sure you want to permanently delete session:\n\n📁 {session_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(folder)
                if state.get("current_session") and os.path.abspath(state["current_session"]) == os.path.abspath(folder):
                    state["current_session"] = None
                    state["csv_paths"] = []
                    state["dataframes"] = {}
                    state["status_counts"] = {}
                    state["fee_schedule"] = {}
                if state.get("_welcome_next_btn"):
                    state["_welcome_next_btn"].setEnabled(False)
                if callable(state.get("refresh_current_session_label")):
                    state["refresh_current_session_label"]()
                for fn in state.get("_refresh_crud_banners", []):
                    fn()
                state["signals"].sessionsChanged.emit()
                state["signals"].dataChanged.emit()
                QMessageBox.information(container, "Deleted", f"Deleted session:\n{session_name}")
            except Exception as e:
                QMessageBox.critical(container, "Delete Failed", f"Could not delete session:\n\n{e}")

    #anklebar_menu.addAction(QAction("Home", container, triggered=open_folder_dialog)) Placeholder for now
    anklebar_menu.addAction(QAction("Load Session Folder", container, triggered=open_folder_dialog))
    anklebar_menu.addAction(QAction("Delete Session Folder", container, triggered=delete_session_dialog))
    anklebar_menu.addAction(QAction("Reset Session", container, triggered=reset_session_wrapper))
    anklebar_menu.addAction(QAction("Set Data Folder Location", container, triggered=choose_base_path_dialog))

    past_sessions_btn.clicked.connect(launch_graphical_loader)

    # ---------------- Stack + Tabs ----------------
    stack_tabs_container = QWidget()
    stack_tabs_layout = QVBoxLayout(stack_tabs_container)
    stack_tabs_layout.setContentsMargins(0, 0, 0, 0)
    stack_tabs_layout.setSpacing(0)

    state["stack"] = QStackedWidget()
    state["stack"].setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    stack_tabs_layout.addWidget(state["stack"], stretch=0)  # no vertical dominance

    tabs = QTabWidget()
    stack_tabs_layout.addWidget(tabs, stretch=1)  # tabs should grow

    main_layout.addWidget(stack_tabs_container)

    state["tabs"] = tabs

    tabs.addTab(create_program_flow_tab(state, state["stack"]), "Program")
    tabs.addTab(create_current_session_files_tab(state), "Current Session Files")
    tabs.addTab(create_all_sessions_tab(state), "All Sessions")
    tabs.addTab(create_any_file_viewer_tab(state), "Browse All Files")

    def refresh_dynamic_tab(index):
        widget = tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    tabs.currentChanged.connect(refresh_dynamic_tab)

    def track_graphical_loader_change(index):
        current_widget = state["stack"].widget(index)
        for i in range(state["stack"].count()):
            widget = state["stack"].widget(i)
            if hasattr(widget, "is_graphical_loader") and widget.is_graphical_loader:
                past_sessions_btn.setEnabled(current_widget != widget)
                break

    state["stack"].currentChanged.connect(track_graphical_loader_change)

    container.setMinimumSize(1000, 700)
    container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    return container

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

    main_widget = create_main_window()

    # Hook up dynamic refresh
    def refresh_dynamic_tab(index):
        tab_widget = main_widget.findChild(QTabWidget)
        if not tab_widget:
            return
        widget = tab_widget.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    tab_widget = main_widget.findChild(QTabWidget)
    if tab_widget:
        tab_widget.currentChanged.connect(refresh_dynamic_tab)

    main_widget.setWindowTitle("AnkleBreaker")
    main_widget.resize(1900, 1000)
    main_widget.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
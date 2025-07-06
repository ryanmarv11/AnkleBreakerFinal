# Standard library imports
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Third-party imports
import pandas as pd

# PyQt6 imports
from PyQt6.QtCore import QDate, QObject, QEvent, Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QIntValidator, QColor
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
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
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


class AppSignals(QObject):
    sessionsChanged = pyqtSignal()   # new/edited/deleted session folders
    clubsChanged    = pyqtSignal()   # club added/removed
    dataChanged     = pyqtSignal()   # statuses, fees, etc. tweaked


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

def is_file_flagged(df: pd.DataFrame) -> bool:
    return "current_status" in df.columns and (df["current_status"] == "other").any()

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

def create_graphical_loader_screen(stack: QStackedWidget, state: Dict) -> QWidget:
    scr = QWidget()
    layout = QVBoxLayout(scr)
    layout.setContentsMargins(12, 12, 12, 12)

    # Back to Welcome button (top-left)
    top_bar = QHBoxLayout()
    top_bar.setContentsMargins(0, 0, 0, 0)

    back_to_welcome_btn = QToolButton()
    back_to_welcome_btn.setText("← Previous Screen")
    back_to_welcome_btn.setStyleSheet("""
        QToolButton {
            background-color: #5b7db1;
            color: white;
            border-radius: 6px;
            padding: 4px 10px;
        }
        QToolButton:hover {
            background-color: #486a9c;
        }
    """)
    def go_back_to_previous():
        previous = state.get("previous_screen_index", 0)
        state["tabs"].setCurrentIndex(0)
        state["stack"].setCurrentIndex(previous)
    back_to_welcome_btn.clicked.connect(go_back_to_previous)

    top_bar.addWidget(back_to_welcome_btn)
    top_bar.addStretch()
    layout.addLayout(top_bar)

    # Header
    # Secondary back button (between club and session views)
    back_btn = QToolButton()
    back_btn.setText("← Back")
    back_btn.setVisible(False)
    back_btn.setStyleSheet("""
        QToolButton {
            background-color: #5b7db1;
            color: white;
            border-radius: 6px;
            padding: 4px 10px;
        }
        QToolButton:hover {
            background-color: #486a9c;
        }
    """)

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
        back_to_welcome_btn.setVisible(True)  # ✅ Show only at top-level
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
        back_to_welcome_btn.setVisible(False)  # ✅ Hide when inside a club
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
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=4)
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
                    state["current_session"] = None
                    state["csv_paths"] = []
                    state["dataframes"] = {}
                    state["status_counts"] = {}
                    state["fee_schedule"] = {}
                    parent = scr
                    while parent is not None:
                        if hasattr(parent, "current_session_label"):
                            parent.current_session_label.setText("No current session")
                            break
                        parent = parent.parent()
                QMessageBox.information(scr, "Deleted", "Session deleted successfully.")
                selected_session_label.setText("Selected Session: None")
                for btn in [mark_paid_btn, mark_unpaid_btn, delete_session_btn]:
                    btn.setEnabled(False)
                state["_selected_session_path"] = None
                state["signals"].sessionsChanged.emit()
                show_sessions_for_club(header.text().split("Sessions for ")[-1])
            except Exception as e:
                QMessageBox.critical(scr, "Error", f"Could not delete session: {e}")

    mark_paid_btn.clicked.connect(lambda: update_paid_status(selected_session_label.session_path, True))
    mark_unpaid_btn.clicked.connect(lambda: update_paid_status(selected_session_label.session_path, False))
    delete_session_btn.clicked.connect(lambda: delete_session(selected_session_label.session_path))

    back_btn.clicked.connect(show_club_buttons)
    show_club_buttons()
    scr.is_graphical_loader = True
    return scr

class WheelEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            return True  # Block the wheel event
        return super().eventFilter(obj, event)


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
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
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

    select_files_btn = QPushButton("Select CSV Files")
    select_folder_btn = QPushButton("Select Folder")
    layout.addWidget(select_files_btn)
    layout.addWidget(select_folder_btn)
    state["_upload_files_btn"] = select_files_btn
    state["_upload_folder_btn"] = select_folder_btn


    # --- ADDED BUTTON ---
    graphical_loader_btn = QPushButton("Past Club Sessions")
    layout.addWidget(graphical_loader_btn)

    next_btn.clicked.connect(lambda: stack.setCurrentIndex(1))

    def open_graphical_loader():
        state["previous_screen_index"] = stack.currentIndex()
        scr = create_graphical_loader_screen(stack, state)
        stack.addWidget(scr)
        stack.setCurrentWidget(scr)

    graphical_loader_btn.clicked.connect(open_graphical_loader)

    # Track last opened timestamp
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
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Could not update last_opened for {session_path}: {e}")

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
                df["AnkleBreaker Notes"] = ""
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

    def select_files():
        paths, _ = QFileDialog.getOpenFileNames(
            screen, "Select CSV Files", "", "CSV Files (*.csv);;All Files (*)"
        )
        if paths:
            load_paths(paths)

    def select_folder():
        start_dir = str(SESSIONS_DIR) if os.path.exists(SESSIONS_DIR) else str(BASE_DIR)
        folder = QFileDialog.getExistingDirectory(screen, "Select Folder Containing CSV Files", start_dir)
        if folder:
            paths = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(".csv")
            ]
            if paths:
                load_paths(paths)

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
            try:
                with open(meta_path, "r") as f:
                    metadata = json.load(f)
                last_opened = metadata.get("last_opened", "1970-01-01T00:00:00")
                sessions_with_time.append((session_name, last_opened))
            except Exception as e:
                print(f"[ERROR] Could not read metadata for {session_name}: {e}")

        sessions_with_time.sort(key=lambda x: x[1], reverse=True)

        for session_name, _ in sessions_with_time:
            session_path = os.path.join(SESSIONS_DIR, session_name)
            meta_path = os.path.join(session_path, "metadata", "metadata.json")
            csv_path = os.path.join(session_path, "csv")
            try:
                with open(meta_path, "r") as f:
                    metadata = json.load(f)
                paid_status = metadata.get("paid", False)
            except Exception as e:
                print(f"[ERROR] Could not read metadata for {session_name}: {e}")
                paid_status = False

            status_text = "paid ✅" if paid_status else "unpaid ❌"
            net_total = metadata.get("net_to_club", "No total yet")
            display_name = f"{session_name} — {status_text} — Total: {net_total}"

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

    return screen

#This is the second screen that the user sees and after clicking next is the point of no return
def create_session_creation_screen(stack: QStackedWidget, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)
    state["_wheel_filter"] = state.get("_wheel_filter") or WheelEventFilter()
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

    next_btn = QPushButton("Next")
    next_btn.setEnabled(False)  # <--- disabled until session is created
    next_btn.clicked.connect(lambda: stack.setCurrentIndex(2))
    left_layout.addWidget(next_btn)
    state["_create_session_next_btn"] = next_btn  # Optional: store for later reference

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
                df["default_status"] = df["Notes"].apply(determine_default_status)

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
            session_path = final_session_path

        metadata = {
            "club": club_name,
            "date": date_str,
            "created": datetime.now().isoformat(),
            "flagged": flagged,
            "flagged_files": flagged_files,
            "fees": {},
        }

        metadata_path = session_path / "metadata" / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)
        

        state["current_session"] = str(session_path)
        state["csv_paths"] = new_paths
        state["dataframes"] = dict(zip(new_paths, state["dataframes"]))  # <-- match paths to DataFrames
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
        assign_screen = create_assign_status_screen(stack, state)
        stack.removeWidget(stack.widget(2))
        stack.insertWidget(2, assign_screen)
        next_btn.setEnabled(True)  # ✅ Enable manual progression after session is created


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
        if not new_club or new_club in state["global_metadata"]["clubs"]:
            return
        state["global_metadata"]["clubs"].append(new_club)
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

        if selected in state["global_metadata"]["clubs"]:
            state["global_metadata"]["clubs"].remove(selected)
            save_global_metadata(state["global_metadata"])
            state["signals"].clubsChanged.emit()

    add_button.clicked.connect(add_club)
    remove_club_btn.clicked.connect(remove_selected_club)

    main_layout.addLayout(left_layout, stretch=2)
    main_layout.addWidget(right_group, stretch=1)

    return screen

def create_payment_summary_screen(stack, state) -> QWidget:
    print("[DEBUG] Status counts keys:", state.get("status_counts", {}).keys())
    print("[DEBUG] Fee schedule keys:", state.get("fee_schedule", {}).keys())

    screen = QWidget()
    layout = QVBoxLayout(screen)

    header = QLabel("Payment Summary")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    # Container layout to be refreshable
    summary_container = QVBoxLayout()
    layout.addLayout(summary_container)

    def build_payment_summary():
        # Clear container
        while summary_container.count():
            child = summary_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # ------------------------------
        # Load Club Name from Metadata
        # ------------------------------
        session_dir = state.get("current_session")
        club_name = "Club"
        if session_dir:
            metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                    club_name = metadata.get("club", "Club")
                except Exception as e:
                    print(f"[ERROR] Failed to read metadata: {e}")

        # ------------------------------
        # Table 1: Status Count Summary
        # ------------------------------
        statuses = ["regular", "manual", "comped", "refund", "waitlist", "other"]
        status_table = QTableWidget()
        status_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

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
        summary_container.addWidget(status_table)

        # ------------------------------
        # Table 2: Financial Breakdown
        # ------------------------------
        summary_container.addWidget(QLabel("Financial Summary"))

        columns = ["Gross", "TrackitHub", "PayPal", club_name]
        financial_table = QTableWidget()
        financial_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        financial_table.setColumnCount(len(columns))
        financial_table.setRowCount(len(filenames) + 1)
        financial_table.setHorizontalHeaderLabels(columns)
        financial_table.setVerticalHeaderLabels(filenames + ["Total"])

        fee_schedule = state.get("fee_schedule", {})
        totals = dict.fromkeys(columns, 0.0)

        for row_idx, fname in enumerate(filenames):
            price = fee_schedule.get(fname, 0)
            counts = status_counts.get(fname, {})

            regular = counts.get("regular", 0)
            manual = counts.get("manual", 0)
            refund = counts.get("refund", 0)

            gross = (regular + manual) * price
            trackithub = (regular + manual) * price * 0.10

            paypal = 0.0
            paypal_count = regular
            for _ in range(paypal_count):
                if price <= 10:
                    paypal += price * 0.05 + 0.09
                else:
                    paypal += price * 0.0349 + 0.49

            net_to_club = gross - trackithub - paypal

            row_values = [gross, trackithub, paypal, net_to_club]
            for col_idx, value in enumerate(row_values):
                item = QTableWidgetItem(f"${value:.2f}")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                financial_table.setItem(row_idx, col_idx, item)
                totals[columns[col_idx]] += value

        for col_idx, col_name in enumerate(columns):
            financial_table.setItem(len(filenames), col_idx, QTableWidgetItem(f"${totals[col_name]:.2f}"))

        financial_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        summary_container.addWidget(financial_table)

    # Build it once on screen creation
    build_payment_summary()

    def refresh_summary():
        new_screen = create_payment_summary_screen(stack, state)
        stack.removeWidget(stack.widget(4))
        stack.insertWidget(4, new_screen)
        stack.setCurrentIndex(4)

    screen.refresh_summary = refresh_summary

    # Navigation
    nav_row = QHBoxLayout()
    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(3))
    nav_row.addWidget(back_btn)
    layout.addLayout(nav_row)

    return screen


#This is the third scrren that the user sees and is the first step after a session is created
#A user cannot backtrack past this screen
def create_assign_status_screen(stack, state) -> QWidget:
    screen = QWidget()
    main_layout = QHBoxLayout(screen)
    state["_wheel_filter"] = state.get("_wheel_filter") or WheelEventFilter()

    # Left layout
    left_layout = QVBoxLayout()
    lbl = QLabel()
    screen.session_label = lbl
    is_flagged = any("-flag.csv" in os.path.basename(p) for p in state.get("csv_paths", []))
    lbl.setText(f"Status Assignment {'FLAGGED' if is_flagged else ''}")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    left_layout.addWidget(lbl)

    file_dropdown = QComboBox()
    file_dropdown.installEventFilter(state["_wheel_filter"])
    left_layout.addWidget(file_dropdown)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)

    scroll_content = QWidget()
    scroll_layout = QVBoxLayout(scroll_content)
    scroll_content.setLayout(scroll_layout)

    # 👇 Key line for consistency
    scroll_content.setMinimumWidth(760)  # or whatever matches View All layout width

    scroll.setWidget(scroll_content)
    left_layout.addWidget(scroll)
    
    next_btn = QPushButton("Next")

    left_layout.addWidget(next_btn)


    # Right layout (Other display)
    right_layout = QVBoxLayout()
    other_display = QTextEdit()
    other_display.setReadOnly(True)
    right_layout.addWidget(QLabel("People with status 'Other' (by file):"))
    right_layout.addWidget(other_display)
    # Get current session folder
    current_session = state.get("current_session")
    csv_paths = state.get("csv_paths", [])
    dataframes_dict = state.get("dataframes", {})

    # NEW: Try using state values if already populated
    if csv_paths and isinstance(dataframes_dict, dict) and all(p in dataframes_dict for p in csv_paths):
        session_csvs = [os.path.basename(p) for p in csv_paths]
        dataframes = [dataframes_dict[p] for p in csv_paths]
    else:
        # Fallback to loading from disk
        session_csvs = []
        dataframes = []
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
                            csv_paths.append(path)
                            dataframes_dict[path] = df
                    except Exception as e:
                        print(f"Error reading {path}: {e}")
        state["csv_paths"] = csv_paths
        state["dataframes"] = dataframes_dict

    print("DEBUG CSV Paths:", csv_paths)
    print("DEBUG DataFrames:", [list(df.columns) for df in dataframes])

    # Now continue with original function logic...
    state["status_counts"] = {}
    def propagate_file_rename(old_path: str, new_path: str, state: Dict, stack: QStackedWidget):
                    print("[DEBUG] Final csv_paths in state:", state["csv_paths"])
                    print("[DEBUG] Final fee_schedule keys:", state.get("fee_schedule", {}).keys())
                    print("[DEBUG] Final status_counts keys:", state.get("status_counts", {}).keys())

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
                    # Refresh screens
                    for screen_index in [2, 3, 4]:
                        widget = stack.widget(screen_index)

                        if screen_index == 2 and hasattr(widget, "refresh_file_dropdown"):
                            widget.refresh_file_dropdown()
                            print("[DEBUG] Refreshed assign status screen dropdown and label")
                        elif screen_index == 3:
                            new_screen = create_fee_schedule_screen(stack, state)
                            stack.removeWidget(widget)
                            stack.insertWidget(3, new_screen)
                            print("[DEBUG] Recreated fee schedule screen at index 3 after rename")
                        elif screen_index == 4:
                            summary_screen = create_payment_summary_screen(stack, state)
                            stack.removeWidget(stack.widget(4))
                            stack.insertWidget(4, summary_screen)
                            print("[DEBUG] Recreated payment summary screen at index 4 after rename")
                        else:
                            print(f"[WARNING] Screen at index {screen_index} does not support refresh.")

                    # Emit signal to trigger any reactive UI
                    state["signals"].sessionsChanged.emit()  # ✅ triggers QTreeWidgets
                    state["signals"].dataChanged.emit()

    def update_flag_state_for_file(csv_path, state, stack):
        df = state["dataframes"].get(csv_path)
        if df is None:
            print(f"[WARNING] No dataframe found for: {csv_path}")
            return

        still_flagged = (df["current_status"] == "other").any()
        is_flagged_file = "-flag.csv" in os.path.basename(csv_path)

        session_path = os.path.dirname(os.path.dirname(csv_path))
        csv_dir = os.path.join(session_path, "csv")
        original_session = state.get("current_session")
        meta_path = os.path.join(session_path, "metadata", "metadata.json")

        old_basename = os.path.basename(csv_path)
        unflagged_path = re.sub(r"-flag(?=\.csv$)", "", csv_path)
        new_basename = os.path.basename(unflagged_path)

        # Load metadata BEFORE changing session path
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {}

        if is_flagged_file and not still_flagged:
            # --------------------------------------------
            # Step 1: Rename the file
            # --------------------------------------------
            if os.path.exists(csv_path):
                try:
                    os.rename(csv_path, unflagged_path)
                    print(f"[RENAME] {csv_path} → {unflagged_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to rename file: {e}")
            else:
                print(f"[WARNING] File to rename not found: {csv_path}")

            # --------------------------------------------
            # Step 2: Update metadata (in memory only)
            # --------------------------------------------
            fees = metadata.get("fees", {})
            if old_basename in fees:
                fees[new_basename] = fees.pop(old_basename)

            if "flagged_files" in metadata and old_basename in metadata["flagged_files"]:
                metadata["flagged_files"].remove(old_basename)

            metadata["flagged"] = False

            # --------------------------------------------
            # Step 3: Update state paths
            # --------------------------------------------
            propagate_file_rename(csv_path, unflagged_path, state, stack)

            # --------------------------------------------
            # Step 4: Delete any leftover -flag.csv files
            # --------------------------------------------
            if os.path.exists(csv_dir):
                for fname in os.listdir(csv_dir):
                    if fname.endswith("-flag.csv"):
                        full_path = os.path.join(csv_dir, fname)
                        if full_path not in state["csv_paths"]:
                            try:
                                os.remove(full_path)
                                print(f"[CLEANUP] Removed leftover flagged file: {full_path}")
                            except Exception as e:
                                print(f"[WARNING] Could not delete leftover flagged file: {e}")
            else:
                print(f"[SKIP] csv_dir no longer exists: {csv_dir}")

            # --------------------------------------------
            # Step 5: Rename the session folder if needed
            # --------------------------------------------
            if "-flag" in original_session and not metadata["flagged"]:
                new_session_path = original_session.replace("-flag", "")
                if os.path.exists(original_session) and not os.path.exists(new_session_path):
                    try:
                        os.rename(original_session, new_session_path)
                        print(f"[FOLDER RENAME] {original_session} → {new_session_path}")
                        state["current_session"] = new_session_path

                        # Update all paths in state
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

                        # Replace the session_path and meta_path for saving
                        session_path = new_session_path
                        meta_path = os.path.join(session_path, "metadata", "metadata.json")

                        # Delete the old session folder if it still exists
                        if os.path.exists(original_session):
                            shutil.rmtree(original_session)
                            print(f"[CLEANUP] Deleted old folder: {original_session}")

                    except Exception as e:
                        print(f"[ERROR] Failed to rename or clean up session folder: {e}")

            # --------------------------------------------
            # Step 6: Save metadata to the correct path
            # --------------------------------------------
            try:
                os.makedirs(os.path.dirname(meta_path), exist_ok=True)
                with open(meta_path, "w") as f:
                    json.dump(metadata, f, indent=2)
            except Exception as e:
                print(f"[ERROR] Failed to write updated metadata: {e}")

            # Final UI & signal refresh
            if callable(state.get("refresh_current_session_label")):
                state["refresh_current_session_label"]()

            state["signals"].sessionsChanged.emit()
            state["signals"].dataChanged.emit()

        elif not is_flagged_file and still_flagged:
            assign_screen = stack.widget(2)
            if hasattr(assign_screen, "session_label"):
                assign_screen.session_label.setText("Status Assignment FLAGGED")
            print("[INFO] File should be re-flagged, but that flow isn’t implemented.")
        else:
            print("[INFO] No rename or cleanup necessary.")

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

    def update_person_buttons(df_index):
        while scroll_layout.count():
            child = scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        selected_file = file_dropdown.currentText()

        if selected_file == "View All":
            grouped_rows = defaultdict(list)

            for path in state["csv_paths"]:
                df = state["dataframes"][path].copy()
                basename = os.path.basename(path)
                df["__source_file__"] = basename
                grouped_rows[basename].extend(df.to_dict("records"))

            for fname in sorted(grouped_rows):
                header_label = QLabel(f"======== {fname} ========")
                header_label.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 6px;")
                scroll_layout.addWidget(header_label)

                for row in grouped_rows[fname]:
                    person_box = QVBoxLayout()
                    person_label = QLabel(f"{row['Name']} — Default: {row['default_status']}")
                    person_box.addWidget(person_label)

                    button_row = QHBoxLayout()
                    statuses = ["regular", "manual", "comped", "refund", "waitlist", "other"]
                    button_group = QButtonGroup(screen)
                    button_group.setExclusive(True)

                    for status in statuses:
                        btn = QPushButton(status.replace("_", " ").capitalize())
                        btn.setCheckable(True)
                        btn.setFixedWidth(90)
                        if row["current_status"] == status:
                            btn.setChecked(True)

                        def make_handler(status=status, person=row):
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

                        btn.clicked.connect(make_handler())
                        button_group.addButton(btn)
                        button_row.addWidget(btn)

                    button_row_widget = QWidget()
                    button_row_widget.setLayout(button_row)
                    button_row_widget.setMaximumWidth(600)
                    person_box.addWidget(button_row_widget)

                    wrapper = QFrame()
                    wrapper.setLayout(person_box)
                    wrapper.setFrameShape(QFrame.Shape.Box)
                    scroll_layout.addWidget(wrapper)

            update_status_counts()
            return

        # Single-file view
        if df_index == 0 or df_index > len(dataframes):
            print(f"[WARNING] Invalid df_index={df_index} for dataframes list of size {len(dataframes)}")
            return

        try:
            path = state["csv_paths"][df_index - 1]
            df = state["dataframes"][path]
        except IndexError:
            print(f"[ERROR] df_index={df_index} is out of range for csv_paths: {state['csv_paths']}")
            return
        except KeyError:
            print(f"[ERROR] No dataframe found for path: {path}")
            return


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
                        selected_file = file_dropdown.currentText()
                        try:
                            df_index = session_csvs.index(selected_file)
                        except ValueError:
                            print(f"[ERROR] Could not find selected file {selected_file} in session_csvs")
                            return

                        path = state["csv_paths"][df_index]
                        df.at[row_idx, "current_status"] = status
                        update_other_display()
                        update_status_counts()
                        update_flag_state_for_file(path, state, stack)
                        state["signals"].dataChanged.emit()
                    return handler

                btn.clicked.connect(make_click_handler())
                button_group.addButton(btn)
                button_row.addWidget(btn)

            # Wrap button row just like in "View All"
            button_row_widget = QWidget()
            button_row_widget.setLayout(button_row)
            button_row_widget.setMaximumWidth(600)  # Match View All
            person_box.addWidget(button_row_widget)

            wrapper = QFrame()
            wrapper.setLayout(person_box)
            wrapper.setFrameShape(QFrame.Shape.Box)
            scroll_layout.addWidget(wrapper)

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
    main_layout.addLayout(left_layout, stretch=3)
    main_layout.addLayout(right_layout, stretch=1)
    def refresh_file_dropdown():
        current_index = file_dropdown.currentIndex()
        file_dropdown.clear()
        file_dropdown.addItem("View All")
        session_csvs[:] = [os.path.basename(p) for p in state["csv_paths"]]
        dataframes[:] = [state["dataframes"][p] for p in state["csv_paths"]]
        file_dropdown.addItems(session_csvs)
        selected_text = file_dropdown.itemText(current_index)
        if selected_text == "View All":
            file_dropdown.setCurrentText("View All")
            update_person_buttons(0)
        elif selected_text in session_csvs:
            index = session_csvs.index(selected_text) + 1  # +1 for View All offset
            file_dropdown.setCurrentIndex(index)
            update_person_buttons(index)
        else:
            print(f"[WARNING] Unexpected dropdown text: {selected_text}")
            update_person_buttons(0)

        update_other_display()
        # Update label after potential unflagging
        session_dir = state.get("current_session", "")
        is_flagged = "-flag" in session_dir or any("-flag.csv" in p for p in state.get("csv_paths", []))
        screen.session_label.setText(f"Status Assignment {'FLAGGED' if is_flagged else ''}")
        # Force dropdown reset and rerender for View All consistency
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

    validator = QIntValidator()
    validator.setBottom(1)

    csv_paths = state.get("csv_paths", [])
    saved_prices = {}
    nav_row = QHBoxLayout()

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(lambda: stack.setCurrentIndex(2))
    nav_row.addWidget(back_btn)

    next_btn = QPushButton("Next")
    next_btn.setEnabled(False)
    def save_and_continue():
        for fname, inp in fee_inputs.items():
            text = inp.text()
            if text.isdigit():
                state["fee_schedule"][fname] = int(text)

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
        all_filled = all(inp.text().isdigit() for inp in fee_inputs.values())
        next_btn.setEnabled(all_filled)


    if not csv_paths:
        layout.addWidget(QLabel("⚠️ No CSV files found for this session."))
    else:
        for path in csv_paths:
            fname = os.path.basename(path)
            inp = QLineEdit()
            inp.setValidator(validator)
            inp.setPlaceholderText("Enter cost")
            if fname in saved_prices:
                inp.setText(str(saved_prices[fname]))
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
        prices = {}
        for fname, inp in fee_inputs.items():
            text = inp.text()
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
            # Calculate net_to_club using same logic as in payment summary
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

            # Save metadata
            with open(metadata_path, "r") as f:
                meta = json.load(f)
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
        val = bulk_input.text()
        if val:
            for field in fee_inputs.values():
                field.setText(val)
        save_fee_schedule()
        update_next_button_state()

    def reset_all():
        bulk_input.clear()
        for field in fee_inputs.values():
            field.clear()
        state["fee_schedule"].clear()
        save_fee_schedule()
        update_next_button_state()

    assign_all_btn = QPushButton("Assign All")
    assign_all_btn.clicked.connect(assign_all)
    layout.addWidget(assign_all_btn)

    reset_all_btn = QPushButton("Reset All")
    reset_all_btn.clicked.connect(reset_all)
    layout.addWidget(reset_all_btn)

    save_btn = QPushButton("Save Fee Schedule")
    save_btn.clicked.connect(save_fee_schedule)
    layout.addWidget(save_btn)

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
                inp.setText(str(saved_price))
            file_form.addRow(QLabel(fname), inp)
            fee_inputs[fname] = inp
        update_next_button_state()

    screen.refresh_file_dropdown = refresh_file_dropdown

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


def create_flagged_sessions_tab(state: Dict) -> QWidget:

    class FlaggedTabSignals(QObject):
        fileDoubleClicked = pyqtSignal(str)

    flagged_signals = FlaggedTabSignals()
    state["flagged_tab_signals"] = flagged_signals

    scr = QWidget()
    layout = QVBoxLayout(scr)

    header = QLabel("Flagged Sessions Overview")
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addWidget(tree)

    # Edit & Unflag UI
    edit_box = QGroupBox("Edit Notes and Unflag")
    edit_layout = QFormLayout(edit_box)

    selected_file_label = QLabel("Selected file: None")
    edit_layout.addRow(selected_file_label)

    name_dropdown = QComboBox()
    abnote_input = QLineEdit()
    save_btn = QPushButton("Save Note")
    edit_layout.addRow("Select Name:", name_dropdown)
    edit_layout.addRow("AnkleBreaker Note:", abnote_input)
    edit_layout.addWidget(save_btn)
    layout.addWidget(edit_box)
    edit_box.setEnabled(False)

    selected_session = None
    selected_file = None
    df = None

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
                    paid_status = metadata.get("paid", False)
                    status_str = "paid ✅" if paid_status else "unpaid ❌"
                    net = metadata.get("net_to_club", None)
                    formatted_total = f"${net:.2f}" if isinstance(net, (int, float)) else "No total yet"
                    display_name = f"{session_name} — {status_str} — total {formatted_total}"

                    parent_item = QTreeWidgetItem([display_name])
                    flagged_files = metadata.get("flagged_files", [])
                    for file_name in flagged_files:
                        file_item = QTreeWidgetItem(parent_item, [file_name])
                        full_path = os.path.join(session_path, "csv", file_name)
                        file_item.setData(0, Qt.ItemDataRole.UserRole, full_path)
                    tree.addTopLevelItem(parent_item)

            except Exception as e:
                print(f"Error reading {metadata_path}: {e}")

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
            else:
                print(f"[ERROR] 'Name' column missing in {full_path}")

        except Exception as e:
            print(f"[ERROR] Failed to load {full_path}: {e}")
            df = None
            edit_box.setEnabled(False)

    def on_tree_item_double_clicked(item: QTreeWidgetItem, column: int):
        parent = item.parent()
        if parent is None:
            return
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path and os.path.exists(file_path):
            state["tabs"].setCurrentIndex(4)
            flagged_signals.fileDoubleClicked.emit(file_path)

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
        df.loc[df["Name"] == name, "AnkleBreaker notes"] = abnote_input.text()

        df["default_status"] = df["Notes"].apply(determine_default_status)

        session_path = os.path.join(SESSIONS_DIR, selected_session)
        csv_dir = os.path.join(session_path, "csv")
        old_path = os.path.join(csv_dir, selected_file)
        df.to_csv(old_path, index=False)

        should_flag = (df["default_status"] == "other").any()
        base_name = selected_file.replace("-flag.csv", ".csv") if selected_file.endswith("-flag.csv") else selected_file
        new_file_name = base_name.replace(".csv", "-flag.csv") if should_flag else base_name
        new_path = os.path.join(csv_dir, new_file_name)

        if old_path != new_path:
            os.rename(old_path, new_path)

        meta_path = os.path.join(session_path, "metadata", "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
            all_files = os.listdir(csv_dir)
            flagged_files = [f for f in all_files if f.endswith("-flag.csv")]
            meta["flagged_files"] = flagged_files
            meta["flagged"] = bool(flagged_files)

            current_name = os.path.basename(session_path)
            new_session_name = current_name.replace("-flag", "") if not flagged_files else (
                current_name if "-flag" in current_name else f"{current_name}-flag"
            )
            if new_session_name != current_name:
                new_session_path = os.path.join(SESSIONS_DIR, new_session_name)
                os.rename(session_path, new_session_path)
                selected_session = new_session_name
                session_path = new_session_path
                state["current_session"] = new_session_path

            with open(os.path.join(SESSIONS_DIR, selected_session, "metadata", "metadata.json"), "w") as f:
                json.dump(meta, f, indent=4)

        state["signals"].sessionsChanged.emit()
        state["signals"].dataChanged.emit()
        refresh_flagged()

    tree.itemClicked.connect(on_tree_item_selected)
    tree.currentItemChanged.connect(on_tree_item_selected)

    
    tree.itemDoubleClicked.connect(on_tree_item_double_clicked)
    name_dropdown.currentTextChanged.connect(on_name_selected)
    save_btn.clicked.connect(on_save_note)

    state["signals"].sessionsChanged.connect(refresh_flagged)
    refresh_flagged()

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
        print(f"[DEBUG] Scanning sessions in: {SESSIONS_DIR}")
        for session_name in os.listdir(SESSIONS_DIR):
            session_path = os.path.join(SESSIONS_DIR, session_name)
            print(f"  ├── Checking session: {session_name}")

            if not os.path.isdir(session_path):
                print("     [SKIP] Not a directory")
                continue

            try:
                # Extract club name from session folder name
                parts = session_name.split("-")
                if len(parts) < 3:
                    print("     [SKIP] Invalid session name format")
                    continue
                club = parts[1]
                print(f"     [CLUB] Parsed club: {club}")

                csv_path = os.path.join(session_path, "csv")
                if not os.path.isdir(csv_path):
                    print("     [SKIP] Missing csv folder")
                    continue

                for fname in os.listdir(csv_path):
                    if fname.endswith(".csv"):
                        full_path = os.path.join(csv_path, fname)
                        if os.path.exists(full_path):
                            structure[club][session_name].append((session_path, fname))

            except Exception as e:
                print(f"[ERROR] Skipping session {session_name}: {e}")
                continue

        print(f"[DEBUG] Final club-session-file structure:\n{structure}")
        return structure

    def refresh_dropdowns():
        nonlocal club_session_file_map
        print("[REFRESH] Refreshing Browse All Files tab")
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

    def connect_flagged_tab_signal():
        signals = state.get("flagged_tab_signals")
        if signals:
            signals.fileDoubleClicked.connect(load_file_from_path)

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
    connect_flagged_tab_signal()

    return scr



# ---------------------------------------------------------------------
# Main window builder
# ---------------------------------------------------------------------
def load_session_from_folder(session_dir: str, stack: QStackedWidget, state: Dict, parent_widget: QWidget):
    # This function assumes session_dir is already selected.
    # In the caller, use: start_dir = SESSIONS_DIR if os.path.exists(SESSIONS_DIR) else ANKLEBREAKER_DATA_DIR

    metadata_path = os.path.join(session_dir, "metadata", "metadata.json")
    csv_dir = os.path.join(session_dir, "csv")

    if not os.path.exists(metadata_path) or not os.path.isdir(csv_dir):
        QMessageBox.warning(parent_widget, "Invalid Session", "Selected folder does not appear to be a valid session.")
        return

    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Inline default status logic
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

        # Set metadata and trigger banners
        state["current_session"] = session_dir
        for fn in state.get("_refresh_crud_banners", []):
            fn()

        state["csv_paths"] = []
        state["dataframes"] = {}
        state["status_counts"] = {}

        fee_schedule = metadata.get("fees", {})
        state["fee_schedule"] = {fname: int(val) for fname, val in fee_schedule.items() if str(val).isdigit()}

        filenames = sorted(f for f in os.listdir(csv_dir) if f.endswith(".csv"))

        for fname in filenames:
            path = os.path.join(csv_dir, fname)
            try:
                df = pd.read_csv(path)

                if "default_status" not in df.columns:
                    df["default_status"] = df["Notes"].apply(determine_default_status)

                if "current_status" not in df.columns:
                    df["current_status"] = df["default_status"]

                if "AnkleBreaker Notes" not in df.columns:
                    df["AnkleBreaker Notes"] = ""

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
        df = state["dataframes"][path]
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
    layout = QVBoxLayout(container)

    state: Dict = {}
    state["signals"] = AppSignals()
    state["global_metadata"] = load_global_metadata()
    state["_refresh_crud_banners"] = []

    # --- Top Button Bar (AnkleBar + Past Club Sessions) ---
    top_bar = QHBoxLayout()

    shared_button_style = """
        QPushButton {
            background-color: #5b7db1;
            color: white;
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 6px;
        }
        QPushButton::menu-indicator {
            image: none;
        }
        QPushButton:hover {
            background-color: #486a9c;
        }
    """

    # --- AnkleBar Button with Dropdown ---
    anklebar_btn = QPushButton("📁 AnkleBar ▾")
    anklebar_btn.setFixedHeight(32)
    anklebar_btn.setStyleSheet(shared_button_style)

    anklebar_menu = QMenu()
    anklebar_btn.setMenu(anklebar_menu)

    load_folder_action = QAction("Load Session", container)
    load_folder_action.triggered.connect(lambda: open_folder_dialog())
    anklebar_menu.addAction(load_folder_action)

    reset_session_action = QAction("Reset Session", container)
    reset_session_action.triggered.connect(lambda: reset_session(state["stack"], state, container))
    anklebar_menu.addAction(reset_session_action)

    delete_session_action = QAction("Delete Session", container)
    delete_session_action.triggered.connect(lambda: delete_session_dialog())
    anklebar_menu.addAction(delete_session_action)

    def open_folder_dialog():
        start_dir = str(SESSIONS_DIR) if os.path.exists(SESSIONS_DIR) else str(BASE_DIR)
        folder = QFileDialog.getExistingDirectory(container, "Select Session Folder", start_dir)
        if not folder:
            return
        folder_name = os.path.basename(folder)
        reply = QMessageBox.question(
            container,
            "Confirm Load",
            f"You are about to load session:\n\n📁 {folder_name}\n\nContinue?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Ok:
            load_session_from_folder(folder, state["stack"], state, container)
        else:
            open_folder_dialog()

    def delete_session_dialog():
        start_dir = str(SESSIONS_DIR) if os.path.exists(SESSIONS_DIR) else str(BASE_DIR)
        folder = QFileDialog.getExistingDirectory(container, "Select Session Folder to Delete", start_dir)
        if not folder:
            return
        session_name = os.path.basename(folder)
        reply = QMessageBox.question(
            container,
            "Confirm Delete",
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
                for fn in state.get("_refresh_crud_banners", []):
                    fn()
                state["signals"].sessionsChanged.emit()
                state["signals"].dataChanged.emit()
                QMessageBox.information(container, "Deleted", f"Deleted session:\n{session_name}")
            except Exception as e:
                QMessageBox.critical(container, "Delete Failed", f"Could not delete session:\n\n{e}")

    # --- Past Club Sessions Button (no dropdown, styled the same) ---
    past_sessions_btn = QPushButton("📂 Past Club Sessions")
    past_sessions_btn.setFixedHeight(32)
    past_sessions_btn.setStyleSheet(shared_button_style)
    def launch_graphical_loader():
        state["previous_screen_index"] = state["stack"].currentIndex()
        graphical_screen = create_graphical_loader_screen(state["stack"], state)
        if state["stack"].indexOf(graphical_screen) == -1:
            state["stack"].addWidget(graphical_screen)
        state["tabs"].setCurrentIndex(0)
        state["stack"].setCurrentWidget(graphical_screen)
    past_sessions_btn.clicked.connect(launch_graphical_loader)

    top_bar.addWidget(anklebar_btn)
    top_bar.addWidget(past_sessions_btn)
    top_bar.addStretch()
    layout.addLayout(top_bar)
    

    # --- Session Banner ---
    session_label = QLabel()
    session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(session_label)

    def refresh_session_label():
        path = state.get("current_session")
        session_label.setText(
            f"Current Session: {os.path.basename(path)}"
            if path else "No current session"
        )
    state["refresh_current_session_label"] = refresh_session_label
    state["_refresh_crud_banners"].append(refresh_session_label)
    refresh_session_label()

    # --- Stack + Tabs ---
    stack_wrapper = QWidget()
    stack_layout = QVBoxLayout(stack_wrapper)
    stack_layout.setContentsMargins(0, 0, 0, 0)

    state["stack"] = QStackedWidget()
    stack_layout.addWidget(state["stack"])

    tabs = QTabWidget()
    layout.addWidget(stack_wrapper)
    layout.addWidget(tabs)

    state["tabs"] = tabs

    program_tab = create_program_flow_tab(state, state["stack"])

    tabs.addTab(program_tab, "Program")
    tabs.addTab(create_current_session_files_tab(state), "Current Session Files")
    tabs.addTab(create_flagged_sessions_tab(state), "Flagged")
    tabs.addTab(create_any_file_viewer_tab(state), "Browse All Files")

    def refresh_dynamic_tab(index):
        widget = tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    tabs.currentChanged.connect(refresh_dynamic_tab)
        # --- Disable Past Club Sessions button while on that screen ---
    def track_graphical_loader_change(index):
        current_widget = state["stack"].widget(index)
        graphical_loader_screen = None
        # Try to find the graphical loader screen in stack
        for i in range(state["stack"].count()):
            widget = state["stack"].widget(i)
            if hasattr(widget, "is_graphical_loader") and widget.is_graphical_loader:
                graphical_loader_screen = widget
                break
        if current_widget == graphical_loader_screen:
            past_sessions_btn.setEnabled(False)
        else:
            past_sessions_btn.setEnabled(True)

    state["stack"].currentChanged.connect(track_graphical_loader_change)

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
    main_widget.resize(800, 600)
    main_widget.show()
    sys.exit(app.exec())



if __name__ == "__main__":
    main()

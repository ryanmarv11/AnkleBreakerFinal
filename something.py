"""pyqt6_status_screen.py – function‑based implementation (v2)
Now with *inline* Good/Bad buttons per Person instead of a single toggle.
"""

from __future__ import annotations

import sys
from typing import Callable, Dict

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

__all__ = [
    "create_status_screen",
]


def create_status_screen(
    *,
    stack: QStackedWidget,  # noqa: F841 – kept for API symmetry even if unused here
    file_frames: Dict[str, pd.DataFrame],
    go_back: Callable[[], None],
    go_next: Callable[[], None],
) -> QWidget:
    """Return the status‑editing QWidget with Good/Bad buttons per Person."""

    # ------------------------------------------------------------------
    # Top‑level widget & variable scaffolding
    # ------------------------------------------------------------------
    screen = QWidget()
    main_layout = QVBoxLayout(screen)

    file_combo = QComboBox()
    file_combo.addItems(list(file_frames.keys()))
    main_layout.addWidget(file_combo)

    center = QHBoxLayout()
    main_layout.addLayout(center, stretch=1)

    # Left pane – scroll‑area filled with Person rows
    person_scroll = QScrollArea()
    person_container = QWidget()
    person_layout = QVBoxLayout(person_container)
    person_scroll.setWidget(person_container)
    person_scroll.setWidgetResizable(True)
    center.addWidget(person_scroll, stretch=3)

    # Right pane – per‑file counts list
    counts_list = QListWidget()
    center.addWidget(counts_list, stretch=1)

    # Navigation bar
    nav = QHBoxLayout()
    main_layout.addLayout(nav)

    back_btn = QPushButton("Back")
    back_btn.clicked.connect(go_back)
    nav.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    nav.addStretch()

    next_btn = QPushButton("Next")
    next_btn.clicked.connect(go_next)
    nav.addWidget(next_btn, alignment=Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------
    # Internal helpers (closure‑based)
    # ------------------------------------------------------------------
    current_file: str | None = None  # non‑local mutable state

    def rebuild_person_rows(df: pd.DataFrame) -> None:
        """Regenerate left‑hand rows with name + Good/Bad buttons."""
        while person_layout.count():
            item = person_layout.takeAt(0)
            if w := item.widget():
                w.deleteLater()

        for idx, row in df.iterrows():
            row_widget = QWidget()
            hl = QHBoxLayout(row_widget)
            hl.setContentsMargins(0, 0, 0, 0)

            name_lbl = QLabel(row["name"])
            hl.addWidget(name_lbl)
            hl.addStretch()

            good_btn = QPushButton("Good")
            bad_btn = QPushButton("Bad")

            # Disable the button that matches current status for clarity
            current = row["status"]
            if current == "good":
                good_btn.setEnabled(False)
            else:
                bad_btn.setEnabled(False)

            good_btn.clicked.connect(lambda _=None, i=idx: set_status(i, "good"))
            bad_btn.clicked.connect(lambda _=None, i=idx: set_status(i, "bad"))

            hl.addWidget(good_btn)
            hl.addWidget(bad_btn)

            person_layout.addWidget(row_widget)

        person_layout.addStretch()

    def refresh_counts() -> None:
        counts_list.clear()
        for fname, df in file_frames.items():
            good = (df["status"] == "good").sum()
            bad = (df["status"] == "bad").sum()
            overall = "GOOD" if bad == 0 else "BAD"
            item = QListWidgetItem(f"{fname}: {good}✔  {bad}✖  →  {overall}")
            colour = Qt.GlobalColor.green if bad == 0 else Qt.GlobalColor.red
            item.setForeground(colour)
            counts_list.addItem(item)

    def set_status(index: int, new_status: str) -> None:
        nonlocal current_file
        if current_file is None:
            return
        df = file_frames[current_file]
        df.at[index, "status"] = new_status
        on_file_changed(current_file)  # brute‑force refresh

    def on_file_changed(fname: str) -> None:
        nonlocal current_file
        if not fname:
            return
        current_file = fname
        rebuild_person_rows(file_frames[fname])
        refresh_counts()

    # Hook the combo box
    file_combo.currentTextChanged.connect(on_file_changed)

    # Prime the UI with the first file (if any)
    if file_frames:
        on_file_changed(file_combo.currentText())

    return screen


# ------------------------------------------------------------------
# Quick demo when executed directly
# ------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    stack = QStackedWidget()

    mock_frames: Dict[str, pd.DataFrame] = {
        "alpha.csv": pd.DataFrame(
            [
                {"name": "Alice", "status": "good"},
                {"name": "Bob", "status": "bad"},
                {"name": "Charlie", "status": "good"},
            ]
        ),
        "beta.csv": pd.DataFrame(
            [
                {"name": "Diana", "status": "good"},
                {"name": "Eve", "status": "good"},
            ]
        ),
    }

    screen = create_status_screen(
        stack=stack,
        file_frames=mock_frames,
        go_back=lambda: print("← Back pressed"),
        go_next=lambda: print("Next → pressed"),
    )

    stack.addWidget(screen)
    stack.setWindowTitle("Status wrangler – inline buttons edition")
    stack.resize(900, 600)
    stack.show()

    sys.exit(app.exec())

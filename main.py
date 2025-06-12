import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QStackedWidget
)
from PyQt6.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt
import pandas as pd
from types import SimpleNamespace


def create_welcome_screen(stack, state):
    screen = QWidget()
    layout = QVBoxLayout()

    label = QLabel("Welcome to the Billing Assistant! Index 0, Step 1")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    # Label to show selected file count
    file_label = QLabel("No files selected.")
    layout.addWidget(file_label)

    # Button to open file dialog for multiple files
    select_files_button = QPushButton("Select CSV Files")

    def select_files():
        file_paths, _ = QFileDialog.getOpenFileNames(
            screen,
            "Select CSV Files",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_paths:
            state["csv_paths"] = file_paths
            loaded_dfs = []
            errors = []

            for path in file_paths:
                try:
                    df = pd.read_csv(path)
                    loaded_dfs.append(df)
                except Exception as e:
                    errors.append(f"{path}: {e}")

            # Store either individual DataFrames or one big one
            state["dataframes"] = loaded_dfs
            state["df"] = pd.concat(loaded_dfs, ignore_index=True) if loaded_dfs else None

            status = f"Loaded {len(loaded_dfs)} files"
            if errors:
                status += f" ({len(errors)} failed)"
            file_label.setText(status)

    select_files_button.clicked.connect(select_files)
    layout.addWidget(select_files_button)

    next_button = QPushButton("Next")
    next_button.clicked.connect(lambda: stack.setCurrentIndex(1))
    layout.addWidget(next_button)

    exit_button = QPushButton("Exit Program")
    exit_button.clicked.connect(QApplication.quit)
    layout.addWidget(exit_button)

    screen.setLayout(layout)
    return screen


def create_session_creation_screen(stack):
    screen = QWidget()
    layout = QVBoxLayout()

    label = QLabel("Session Creation (Index 1, Step 2)")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    next_button = QPushButton("Next")
    next_button.clicked.connect(lambda: stack.setCurrentIndex(2))
    next_button.setFixedSize(400,125)
    # You can add logic here for going forward again
    layout.addWidget(next_button)

    back_button = QPushButton("Back")
    back_button.clicked.connect(lambda: stack.setCurrentIndex(0))
    layout.addWidget(back_button)

    screen.setLayout(layout)
    return screen

def create_assign_status_screen(stack):
    screen = QWidget()
    layout = QVBoxLayout()

    label = QLabel("Status Assignment (Index 2, Step 3)")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    next_button = QPushButton("Next")
    #next_button.clicked.connect(lambda: stack.setCurrentIndex(3))
    layout.addWidget(next_button)

    back_button = QPushButton("Back")
    back_button.clicked.connect(lambda: stack.setCurrentIndex(1))
    layout.addWidget(back_button)


    screen.setLayout(layout)
    return screen


def main():
    app = QApplication(sys.argv)
    stack = QStackedWidget()
    state = {}

    welcome_screen = create_welcome_screen(stack, state)
    blank_screen = create_session_creation_screen(stack)
    assign_status_screen = create_assign_status_screen(stack)

    stack.addWidget(welcome_screen)
    stack.addWidget(blank_screen)
    stack.addWidget(assign_status_screen)

    stack.setWindowTitle("Billing Assistant")
    stack.resize(400, 400)
    stack.setCurrentIndex(0)
    stack.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

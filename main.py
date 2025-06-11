import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QStackedWidget
)
from PyQt6.QtCore import Qt


def create_welcome_screen(stack):
    screen = QWidget()
    layout = QVBoxLayout()

    label = QLabel("Welcome to the Billing Assistant!")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    next_button = QPushButton("Next")
    next_button.clicked.connect(lambda: stack.setCurrentIndex(1))
    layout.addWidget(next_button)

    exit_button = QPushButton("Exit Program")
    exit_button.clicked.connect(QApplication.quit)
    layout.addWidget(exit_button)

    screen.setLayout(layout)
    return screen


def create_blank_screen(stack):
    screen = QWidget()
    layout = QVBoxLayout()

    label = QLabel("Blank Screen (Step 2)")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    back_button = QPushButton("Back")
    back_button.clicked.connect(lambda: stack.setCurrentIndex(0))
    layout.addWidget(back_button)

    next_button = QPushButton("Next (Placeholder)")
    # You can add logic here for going forward again
    layout.addWidget(next_button)

    screen.setLayout(layout)
    return screen


def main():
    app = QApplication(sys.argv)
    stack = QStackedWidget()

    welcome_screen = create_welcome_screen(stack)
    blank_screen = create_blank_screen(stack)

    stack.addWidget(welcome_screen)
    stack.addWidget(blank_screen)

    stack.setWindowTitle("Billing Assistant")
    stack.resize(400, 200)
    stack.setCurrentIndex(0)
    stack.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

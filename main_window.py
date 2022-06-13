from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from main_graphics_display import MainGraphicsDisplay


class MainWindow(QMainWindow):
    """Main window copy of Medical Annotation Framework"""
    # TODO: Loading of file
    def __init__(self, *args, file):
        super(MainWindow, self).__init__(*args)
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # enable highdpi scaling
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # use highdpi icons
        self.setWindowTitle("The All-Purpose Labeling Tool")
        self.resize(1276, 968)

        # The main widget set as focus. Based on a horizontal layout
        self.main_widget = QWidget()
        self.main_widget.setLayout(QHBoxLayout())
        self.main_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.main_widget.layout().setSpacing(0)

        # Center Frame of the body where the image will be displayed in
        self.center_frame = QFrame()
        self.center_frame.setLayout(QVBoxLayout())
        self.center_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.center_frame.layout().setSpacing(0)
        self.image_display = MainGraphicsDisplay(file=file)
        self.center_frame.layout().addWidget(self.image_display)

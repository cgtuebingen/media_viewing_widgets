from PyQt5.QtWidgets import *
from slide_view import SlideView
from graphics_view import GraphicsView


class MainGraphicsDisplay(QWidget):
    """Display of the main element"""
    def __init__(self, *args, file):
        super(MainGraphicsDisplay, self).__init__(*args)
        self.scene = QGraphicsScene()
        self.viewer = GraphicsView()
        self.slide_view = SlideView(filepath=file,
                                    width=self.width(),
                                    height=self.height())
        self.slide_view.setParent(self.scene)
        self.slide_view.setParent(self.viewer)
        self.scene.addItem(self.slide_view)

        self.viewer.setFrameShape(QFrame.NoFrame)
        self.viewer.setScene(self.scene)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.viewer)


        # self.viewer.fitInView()

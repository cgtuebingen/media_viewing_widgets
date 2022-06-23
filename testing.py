from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from slide_view import SlideView
from graphics_view import GraphicsView


class BaseGraphicsScene(QGraphicsScene):
    def __init__(self):
        super(BaseGraphicsScene, self).__init__()


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) # enable highdpi scaling
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)    # use highdpi icons
    app = QApplication(['test'])

    viewer = GraphicsView()
    viewer.fitInView()

    scene = BaseGraphicsScene()

    file = QFileDialog().getOpenFileName()[0]
    slide_view = SlideView(filepath=file, width=viewer.viewport().width(), height=viewer.viewport().height())
    slide_view.setParent(scene)
    slide_view.setParent(viewer)

    scene.addItem(slide_view)
    viewer.setScene(scene)

    viewer.show()

    app.exec()

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from media_viewing_widgets_tools.slide_view import SlideView
from graphics_view import GraphicsView


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)     # enable high dpi scaling
    app = QApplication(['test'])

    slide_view = SlideView()

    scene = QGraphicsScene()
    scene.addItem(slide_view)

    viewer = GraphicsView(scene)
    viewer.resize(1000, 600)
    viewer.show()
    slide_view.load_new_image(QFileDialog().getOpenFileName()[0])
    viewer.fitInView()

    app.exec()

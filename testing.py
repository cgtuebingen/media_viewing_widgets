from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import numpy as np
from openslide import OpenSlide
from PIL import Image
from slide_view import SlideView


class GraphicsView(QGraphicsView):
    start_checking = pyqtSignal()

    def __init__(self, *args):
        super(GraphicsView, self).__init__(*args)
        self.setBackgroundBrush(QBrush(QColor("r")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self.start_checking.connect(self.update_check, Qt.ConnectionType.QueuedConnection)

        self.setMouseTracking(True)
        self._pan_start: bool = False
        self._panning: bool = False

        self.update_check()  # called ones to start

    def fitInView(self, *__args):
        if self.scene():
            super(GraphicsView, self).fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        pass

    def resizeEvent(self, event: QResizeEvent):
        """
        currently just fits the view after resizing
        ToDo: fix the problem with large window sizes. If started with a small window size and change into a large one, the images are to small to fit
        """
        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent):
        """
        scales the image and moves into the mouse position
        """
        oldPos = self.mapToScene(event.position().toPoint())
        scale_factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(scale_factor, scale_factor)
        newPos = self.mapToScene(event.position().toPoint())
        move = newPos - oldPos
        self.translate(move.x(), move.y())
        # event.ignore()
        super(GraphicsView, self).wheelEvent(event)

        if hasattr(self.scene().items()[1], "wheel_position_changed"):
            width = self.viewport().width()
            height = self.viewport().height()
            image_pos_upleft = self.mapToScene(0, 0)
            image_pos_lowright = self.mapToScene(width, height)
            self.scene().items()[1].wheel_position_changed(image_pos_upleft, image_pos_lowright, width, height)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = True
            self._pan_start = self.mapToScene(event.pos())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            if hasattr(self.scene().items()[1], "set_image"):
                self.scene().items()[1].set_image()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            new_pos = self.mapToScene(event.pos())
            move = new_pos - self._pan_start
            self.translate(move.x(), move.y())
            self._pan_start = self.mapToScene(event.pos())

        if hasattr(self.scene().items()[1], "mouse_position_changed"):
            self.scene().items()[1].mouse_position_changed(self.mapToScene(event.pos()))

    @pyqtSlot()
    def update_check(self):
        if hasattr(self.scene().items()[1], "update_view"):
            image_pos_upleft = self.mapToScene(0, 0)
            image_pos_lowright = self.mapToScene(self.viewport().width(), self.viewport().height())
            self.scene().items()[1].update_view(image_pos_upleft, image_pos_lowright)
            self.start_checking.emit()


class BaseGraphicsScene(QGraphicsScene):
    def __init__(self):
        super(BaseGraphicsScene, self).__init__()


"""
def show_reference(filepath):
    test_slide = OpenSlide(filepath)
    reference = np.asarray(test_slide.read_region((0, 0), 6, np.array([440, 400])).convert('RGB'))
    img = Image.fromarray(reference)
    img.show()
"""

if __name__ == '__main__':
    app = QApplication(['test'])

    file = r'C:\Users\danie\OneDrive\Dokumente\GitHub\D-Schiller\Implementation\A76_19_1.tiff'
    slide_view = SlideView(filepath=file)

    scene = BaseGraphicsScene()
    scene.addItem(slide_view)
    slide_view.setParent(scene)

    viewer = GraphicsView(scene)
    slide_view.setParent(viewer)
    viewer.show()
    viewer.resize(660, 600)

    app.exec()

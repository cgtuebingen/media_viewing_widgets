from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


class GraphicsView(QGraphicsView):

    def __init__(self, *args):
        super(GraphicsView, self).__init__(*args)
        self.setBackgroundBrush(QBrush(QColor("r")))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)

        self._pan_start: bool = False
        self._panning: bool = False

    def fitInView(self, *__args):
        if self.scene():
            super(GraphicsView, self).fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event: QResizeEvent):
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.children()[3].resize_view()

    def wheelEvent(self, event: QWheelEvent):
        """scales the image and moves into the mouse position"""
        oldPos = self.mapToScene(event.position().toPoint())
        scale_factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(scale_factor, scale_factor)
        newPos = self.mapToScene(event.position().toPoint())
        move = newPos - oldPos
        self.translate(move.x(), move.y())
        super(GraphicsView, self).wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = True
            self._pan_start = self.mapToScene(event.pos())
            super(GraphicsView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            super(GraphicsView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            new_pos = self.mapToScene(event.pos())
            move = new_pos - self._pan_start
            self.translate(move.x()/2, move.y()/2)
            self._pan_start = self.mapToScene(event.pos())
        super(GraphicsView, self).mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_L:
            filepath = QFileDialog().getOpenFileName()[0]
            self.scene().items()[1].load_new_image(filepath=filepath)
            self.fitInView()

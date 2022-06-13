import numpy as np
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
        self.scale_track: float = 1.0
        self.moved_x: float = 0.0
        self.moved_y: float = 0.0

    def fitInView(self, *__args):
        if self.scene():
            self.children()[3].refactor_image()
            self.children()[3].set_image()
            super(GraphicsView, self).fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.children()[3].setPos(-self.moved_x, -self.moved_y)
            self.moved_x = 0.0
            self.moved_y = 0.0

    def resizeEvent(self, event: QResizeEvent):
        if self.scene():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.children()[3].resize_view()

    def wheelEvent(self, event: QWheelEvent):
        """scales the image and moves into the mouse position"""
        old_pos = self.mapToScene(event.position().toPoint())
        scale_factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale_track = self.scale_track * scale_factor
        self.scale(scale_factor, scale_factor)
        if self.scale_track < 1.0:
            self.scale_track = 1.0
            self.fitInView()
            return
        new_pos = self.mapToScene(event.position().toPoint())
        move = new_pos - old_pos
        self.moved_x += move.x()
        self.moved_y += move.y()
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
        if event.key() == Qt.Key_F:
            self.fitInView()
        if event.key() == Qt.Key_T:
            self.translate(10**5, 0)

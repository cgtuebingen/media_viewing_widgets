from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


class GraphicsView(QGraphicsView):

    def __init__(self, *args):
        super(GraphicsView, self).__init__(*args)

        self._pan_start: QPointF = None   # starting point before panning
        self._panning: bool = False     # flag to enable panning

        self.setBackgroundBrush(QBrush(QColor("r")))
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)

    def fitInView(self, *__args):
        if self.scene():    # don't run code without a scene, prevents crashes
            super(GraphicsView, self).fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent):
        """
        Scales the image and moves into the mouse position
        :param event: event to initialize the function
        :type event: QWheelEvent
        :return: /
        """
        old_pos = self.mapToScene(event.pos())
        scale_factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(scale_factor, scale_factor)
        new_pos = self.mapToScene(event.pos())
        move = new_pos - old_pos
        self.translate(move.x(), move.y())
        super(GraphicsView, self).wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """
        Enables panning of the image
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._pan_start = self.mapToScene(event.pos())
        super(GraphicsView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Disables panning of the image
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if event.button() == Qt.LeftButton:
            self._panning = False
        super(GraphicsView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Realizes panning, if activated
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if self._panning:
            new_pos = self.mapToScene(event.pos())
            move = new_pos - self._pan_start
            self.translate(move.x(), move.y())
            self._pan_start = self.mapToScene(event.pos())
        super(GraphicsView, self).mouseMoveEvent(event)


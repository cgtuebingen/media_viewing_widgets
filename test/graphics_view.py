from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


class GraphicsView(QGraphicsView):

    def __init__(self, *args):
        """
        Initialization of the GraphicsView
        :param args: /
        :type args: /
        """
        super(GraphicsView, self).__init__(*args)

        self._pan_start: QPointF = []   # starting point before panning
        self._panning: bool = False     # flag to enable panning

        self.setBackgroundBrush(QBrush(QColor("r")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)

    def loadfile(self):
        """
        Loads a new file
        :return: /
        """
        filepath = QFileDialog().getOpenFileName()[0]
        number_item = 1     # this might change in over applications
        self.scene().items()[number_item].load_new_image(filepath=filepath)
        self.fitInView()

    def fitInView(self, *__args):
        """
        Resets the view to the original size and resets the _slide level
        :param __args: /
        :type __args: /
        :return: /
        """
        if self.scene():    # don't run code without a scene, prevents crashes
            super(GraphicsView, self).fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event: QResizeEvent):
        """
        Calls fitInView after resizing the window
        :param event: event to initialize the function
        :type event: QResizeEvent
        :return: /
        """
        if self.scene():    # don't run code without a scene, prevents crashes
            self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

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
        new_pos = self.mapToScene(event.position().toPoint())
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
        if event.button() == Qt.MouseButton.LeftButton:
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
        if event.button() == Qt.MouseButton.LeftButton:
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

    def keyPressEvent(self, event):
        """
        Calls loadimage if key "l" is pressed
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if event.key() == Qt.Key_L:
            self.loadfile()

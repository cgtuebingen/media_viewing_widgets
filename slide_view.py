from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import numpy as np
from slideloader import SlideLoader


class SlideView(QGraphicsObject):
    start_checking = pyqtSignal()

    def __init__(self, filepath: str, width: int, height: int):
        super(SlideView, self).__init__()
        self.pixmap_item: QGraphicsPixmapItem = QGraphicsPixmapItem(parent=self)
        self.setAcceptHoverEvents(True)
        self.slideloader: SlideLoader = SlideLoader(filepath=filepath, width=width, height=height)
        self.start_checking.connect(self.update_check, Qt.ConnectionType.QueuedConnection)

        self.num_lvl: int = None
        self.slide_lvl: int = None
        self.scene_pos: np.ndarray = None
        self.mouse_pos: np.ndarray = None
        self.refactor_image()
        self.set_image()
        self.update_check()

    def resize_view(self):
        width = self.scene().views()[0].viewport().width()
        height = self.scene().views()[0].viewport().height()
        self.slideloader.update_slide(width=width, height=height)
        self.refactor_image()

    def boundingRect(self):
        return self.childrenBoundingRect()

    def paint(self, p: QPainter, o: QStyleOptionGraphicsItem, widget=None):
        pass

    def load_new_image(self, filepath: str):
        width = self.scene().views()[0].viewport().width()
        height = self.scene().views()[0].viewport().height()
        self.slideloader.set_slide(filepath)
        self.slideloader.update_slide(width=width, height=height)
        self.refactor_image()
        self.set_image()

    def refactor_image(self):
        """
        used for new slides
        """
        self.num_lvl = self.slideloader.num_lvl
        self.slide_lvl = self.slideloader.slide_lvl
        self.scene_pos = self.slideloader.scene_pos
        self.mouse_pos = self.slideloader.mouse_pos

    def set_image(self):
        """
        load the position and data
        """
        self.scene_pos = self.slideloader.zoom_stack[self.slide_lvl]['position']
        image = np.array(self.slideloader.zoom_stack[self.slide_lvl]['data'])

        """
        set the image
        """
        height, width, channel = image.shape
        bytesPerLine = 3 * width
        qimg = QImage(image.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        self.pixmap_item.setPixmap(QPixmap(qimg))

        """
        stretch the image into normed size and set the scene position
        """
        self.setScale(2 ** self.slide_lvl)
        self.setPos(*self.scene_pos)
        self.slideloader.scene_pos = self.scene_pos
        self.slideloader.slide_lvl = self.slide_lvl

    def slide_change(self, slide_change: int):
        self.slide_lvl += slide_change
        print(self.slide_lvl)
        if self.slide_lvl < 0:
            self.slide_lvl = 0 # no image_update if on lowest slide
            pass
        if self.slide_lvl > self.slideloader.num_lvl:
            self.slide_lvl = self.slideloader.num_lvl # no image_update if on highest slide
            pass
        self.set_image()

    @pyqtSlot()
    def update_check(self):
        if self.scene():
            width = self.scene().views()[0].viewport().width()
            height = self.scene().views()[0].viewport().height()

            scene_up_left = self.scene_pos
            scene_low_right = self.scene_pos + self.slideloader.slide_size[self.slide_lvl] * 2 ** self.slide_lvl

            view_up_left = self.scene().views()[0].mapToScene(int(0.02*width), int(0.02*height))
            view_low_right = self.scene().views()[0].mapToScene(int(0.98*width), int(0.98*height))

            if scene_up_left[0] > view_up_left.x() or scene_up_left[1] > view_up_left.y() or \
                    scene_low_right[0] < view_low_right.x() or scene_low_right[1] < view_low_right.y() and \
                    self.slide_lvl != self.num_lvl:
                self.set_image()

        self.start_checking.emit()

    def wheelEvent(self, event: 'QGraphicsSceneWheelEvent'):
        """
        Checks if current or next lower image resolution is high enough for the window size
        """
        width = self.scene().views()[0].viewport().width()
        height = self.scene().views()[0].viewport().height()
        image_pos_upleft = self.scene().views()[0].mapToScene(0, 0)
        image_pos_lowright = self.scene().views()[0].mapToScene(width, height)
        if self.slideloader.dominate_x:  # check for larger dimension
            distance = (image_pos_lowright.x() - image_pos_upleft.x()) / (2 ** self.slide_lvl)
            if distance <= width:
                self.slide_change(int(-1))
            if distance / 2 > width:  # the resolution difference between two slides is "2"
                self.slide_change(int(+1))
        else:
            distance = (image_pos_lowright.y() - image_pos_upleft.y()) / (2 ** self.slide_lvl)
            if distance <= height:
                self.slide_change(int(-1))
            if distance / 2 > height:  # the resolution difference between two slides is "2"
                self.slide_change(int(+1))

    def hoverMoveEvent(self, event: 'QGraphicsSceneHoverEvent') -> None:
        mouse_scene_pos = self.mapToScene(event.pos())
        self.mouse_pos = np.array([mouse_scene_pos.x(), mouse_scene_pos.y()]).astype(int)
        self.slideloader.mouse_pos = self.mouse_pos

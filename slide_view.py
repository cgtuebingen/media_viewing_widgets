from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import numpy as np
from slideloader import SlideLoader


class SlideView(QGraphicsObject):

    def __init__(self, filepath):
        super(SlideView, self).__init__()
        self.pixmap_item: QGraphicsPixmapItem = QGraphicsPixmapItem(parent=self)
        self.slideloader: SlideLoader = None
        self.num_lvl: int = None
        self.slide_lvl: int = None
        self.scene_pos: np.ndarray = None
        self.mouse_pos: np.ndarray = None
        self.scale_factor: int = 0

        self.refactor_image(filepath)
        self.set_image()

    def boundingRect(self):
        return self.childrenBoundingRect()

    def paint(self, p: QPainter, o: QStyleOptionGraphicsItem, widget=None):
        pass

    def refactor_image(self, filepath):
        """
        used for new slides
        """
        self.slideloader = SlideLoader(filepath)
        self.num_lvl = self.slideloader.num_lvl
        self.slide_lvl = self.slideloader.slide_lvl
        self.scene_pos = self.slideloader.scene_pos
        self.mouse_pos = self.slideloader.mouse_pos
        self.scale_factor = 1

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
        if self.slide_lvl < 0:
            self.slide_lvl = 0
            pass    # no image_update if on lowest slide
        if self.slide_lvl > self.slideloader.num_lvl:
            self.slide_lvl = self.slideloader.num_lvl
            pass    # no image_update if on highest slide
        self.set_image()

    def update_view(self, image_pos_upleft: QPoint, image_pos_lowright: QPoint):
        size = (self.slideloader.slide_size[self.slide_lvl] * 2 ** self.slide_lvl)
        scene_pos_upleft = self.scene_pos
        scene_pos_lowright = scene_pos_upleft + size

        if image_pos_upleft.x() < scene_pos_upleft[0] or image_pos_upleft.y() < scene_pos_upleft[1] or \
                image_pos_lowright.x() > scene_pos_lowright[0] or image_pos_lowright.y() > scene_pos_lowright[1]:
            self.set_image()

    def wheelEvent(self, event: 'QGraphicsSceneWheelEvent') -> None:
        pass

    def wheel_position_changed(self, image_pos_upleft: QPoint, image_pos_lowright: QPoint, width: int, height: int):
        """
        Checks if current or next lower image resolution is high enough for the window size
        """
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

    def mouse_position_changed(self, mouse_scene_pos: QPoint):
        self.mouse_pos = np.array([mouse_scene_pos.x(), mouse_scene_pos.y()]).astype(int)
        self.slideloader.mouse_pos = self.mouse_pos

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
        self.start_checking.connect(self.update_image_check, Qt.ConnectionType.QueuedConnection)

        self.num_lvl: int = None
        self.slide_lvl_active: int = None
        self.slide_lvl_goal: int = None
        self.scene_pos: np.ndarray = None
        self.mouse_pos: np.ndarray = None
        self.backup_activ: bool = None
        self.refactor_image()
        self.set_image()

    def resize_view(self):
        width = self.scene().views()[0].viewport().width()
        height = self.scene().views()[0].viewport().height()
        self.slideloader.update_slide_size(width=width, height=height)
        self.refactor_image()

    def boundingRect(self):
        return self.childrenBoundingRect()

    def paint(self, p: QPainter, o: QStyleOptionGraphicsItem, widget=None):
        pass

    def load_new_image(self, filepath: str):
        width = self.scene().views()[0].viewport().width()
        height = self.scene().views()[0].viewport().height()
        self.slideloader.set_slide(filepath)
        self.slideloader.update_slide_size(width=width, height=height)
        self.refactor_image()
        self.set_image()

    def refactor_image(self):
        """ used for new slides"""
        self.num_lvl = self.slideloader.num_lvl
        self.slide_lvl_active = self.slideloader.num_lvl
        self.slide_lvl_goal = self.slideloader.num_lvl
        self.scene_pos = np.array([0, 0])
        self.mouse_pos = self.slideloader.mouse_pos

    def set_image(self):
        """ load the position and data"""
        slides = self.slideloader.get_zoom_stack()
        self.scene_pos = slides[self.slide_lvl_active]['position']
        image = slides[self.slide_lvl_active]['data']

        """set the image"""
        height, width, channel = image.shape
        bytesPerLine = 3 * width
        qimg = QImage(image.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        self.pixmap_item.resetTransform()
        self.pixmap_item.setPixmap(QPixmap(qimg))

        """stretch the image into normed size and set the scene position"""
        self.pixmap_item.setScale(2 ** self.slide_lvl_active)
        self.pixmap_item.setPos(*self.scene_pos)

    def slide_change(self, slide_change: int):
        self.slide_lvl_goal += slide_change
        if self.slide_lvl_goal < 0:
            self.slide_lvl_goal = 0  # no image_update if on lowest slide
            return
        if self.slide_lvl_goal > self.slideloader.num_lvl:
            self.slide_lvl_goal = self.slideloader.num_lvl  # no image_update if on highest slide
            return

    @pyqtSlot()
    def update_image_check(self):
        """This function decides if a new image will be displayed"""
        if self.scene():
            slides = self.slideloader.get_zoom_stack()
            width = self.scene().views()[0].viewport().width()
            height = self.scene().views()[0].viewport().height()
            view_up_left = self.scene().views()[0].mapToScene(int(0.02 * width), int(0.02 * height))    # 2% buffer for frame
            view_low_right = self.scene().views()[0].mapToScene(int(0.98 * width), int(0.98 * height))  # 2% buffer for frame

            for lvl in range(min(self.slide_lvl_goal, self.slide_lvl_active),
                             max(self.slide_lvl_goal, self.slide_lvl_active) + 1):
                """Go through all level from the goal to the current one. If a slide fits completely into the view, 
                display the slide. If no slide fits, stay in the current level, but check if on the current level
                a corner of the view is outside the slide. If so, go one level higher."""
                scene_up_left_goal = slides[lvl]['position']
                scene_low_right_goal = scene_up_left_goal + self.slideloader.slide_size[lvl] * 2 ** lvl

                if (view_up_left.x() > scene_up_left_goal[0] and
                        view_up_left.y() > scene_up_left_goal[1] and
                        view_low_right.x() < scene_low_right_goal[0] and
                        view_low_right.y() < scene_low_right_goal[1]) and \
                        lvl < self.slide_lvl_active:    # to ensure that not every time an image will be displayed
                    self.slide_lvl_active = lvl
                    self.set_image()
                    break
                elif (view_up_left.x() < scene_up_left_goal[0] or
                        view_up_left.y() < scene_up_left_goal[1] or
                        view_low_right.x() > scene_low_right_goal[0] or
                        view_low_right.y() > scene_low_right_goal[1]) and lvl == self.slide_lvl_active:
                    self.slide_lvl_active += 1
                    if self.slide_lvl_active >= self.num_lvl:   # check if you are already on the highest level
                        self.slide_lvl_active = self.num_lvl
                        self.set_image()
                        """Stop the function, if we are on the highest level, no update is required 
                        (Most of the time, the view on the highest level will be outside the slide)"""
                        return
                    self.set_image()
        self.start_checking.emit()

    def wheelEvent(self, event: 'QGraphicsSceneWheelEvent'):
        """Checks if current or next lower image resolution is high enough for the window size"""
        width_view = self.scene().views()[0].viewport().width()
        height_view = self.scene().views()[0].viewport().height()
        image_pos_upleft = self.scene().views()[0].mapToScene(0, 0)
        image_pos_lowright = self.scene().views()[0].mapToScene(width_view, height_view)
        if width_view >= height_view:  # check for larger dimension
            width_image = (image_pos_lowright.x() - image_pos_upleft.x()) / (2 ** self.slide_lvl_active)
            if width_image <= width_view and event.delta() > 0:
                self.slide_change(int(-1))
            if width_image/1.5 > width_view and event.delta() < 0:  # to ensure a hysteresis
                self.slide_change(int(+1))
        else:
            height_image = (image_pos_lowright.y() - image_pos_upleft.y()) / (2 ** self.slide_lvl_active)
            if height_image <= height_view and event.delta() > 0:
                self.slide_change(int(-1))
            if height_image/1.5 > height_view and event.delta() < 0:  # to ensure a hysteresis
                self.slide_change(int(+1))
        """idea: put active slide lvl on the largest one and ensure image is displayed;
        let the @update_check find the best lvl"""
        self.slide_lvl_active = self.num_lvl
        self.start_checking.emit()  # restart the update (after pausing on highest level)

    def mouseReleaseEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """always add a level after panning to prevent unloaded data"""
        self.slide_lvl_active = min([self.slide_lvl_active + 1, self.num_lvl])
        self.set_image()

    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """function needs to be implemented for other QGraphicsSceneMouseEvent"""
        pass

    def hoverMoveEvent(self, event: 'QGraphicsSceneHoverEvent'):
        mouse_scene_pos = self.mapToScene(event.pos())
        self.mouse_pos = np.array([mouse_scene_pos.x(), mouse_scene_pos.y()]).astype(int)
        self.slideloader.mouse_pos = self.mouse_pos

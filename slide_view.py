from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import numpy as np
from slideloader import SlideLoader


class SlideView(QGraphicsObject):
    start_checking = pyqtSignal()

    def __init__(self, filepath: str, width: int, height: int):
        """
        Initialization of SlideView. Important: The Graphicsview initialized first, because the SlideLoader needs the
        size to calculate the size of the different slide levels.
        :param filepath: path of the slide data.
        :type filepath: str
        :param width: width of the GraphicsView
        :type width: int
        :param height: height of the GraphicView
        :type height: int
        """
        super(SlideView, self).__init__()

        self.slide_loader: SlideLoader = SlideLoader(filepath=filepath, width=width, height=height)
        self.num_lvl: int = self.slide_loader.num_lvl             # total number of slide level
        self.slide_lvl_active: int = self.slide_loader.num_lvl    # number of current displayed slide level
        self.slide_lvl_goal: int = self.slide_loader.num_lvl      # number of wanted slide level after zooming
        self.scene_pos: np.ndarray = np.array([0, 0])             # upper right position of the scene
        self.mouse_pos: np.ndarray = self.slide_loader.mouse_pos  # current mouse position on the scene
        self.view_width: int = width                              # width of the GraphicsView
        self.view_height: int = height                            # height of the GraphicsView

        self.pixmap_item: QGraphicsPixmapItem = QGraphicsPixmapItem(parent=self)
        self.setAcceptHoverEvents(True)
        self.start_checking.connect(self.update_image_check, Qt.ConnectionType.QueuedConnection)

        self.set_image()

    def boundingRect(self):
        """
        Needs to be included
        :return: /
        """
        return self.childrenBoundingRect()

    def paint(self, p: QPainter, o: QStyleOptionGraphicsItem, widget=None):
        """
        Needs to be included
        :return: /
        """
        pass

    def load_new_image(self, filepath: str):
        """
        Loads and displays a new image
        :param filepath: path of the slide data.
        :type filepath: str
        :return:
        """
        self.slide_loader.set_slide(filepath)
        self.refactor_image()
        self.set_image()

    def refactor_image(self):
        """
        Resets the metadata of a slide after loading a new one or resizing the view.
        :return:
        """
        self.view_width = self.scene().views()[0].viewport().width()
        self.view_height = self.scene().views()[0].viewport().height()
        self.slide_loader.update_slide_size(width=self.view_width, height=self.view_height)
        self.num_lvl = self.slide_loader.num_lvl
        self.slide_lvl_active = self.slide_loader.num_lvl
        self.slide_lvl_goal = self.slide_loader.num_lvl
        self.scene_pos = np.array([0, 0])
        self.mouse_pos = self.slide_loader.mouse_pos

    def set_image(self):
        """
        Displays the image and handles the scene position of the new image
        :return: /
        """
        # load position and data
        slides = self.slide_loader.get_zoom_stack()
        self.scene_pos = slides[self.slide_lvl_active]['position']
        image = slides[self.slide_lvl_active]['data']

        # set the image
        height, width, channel = image.shape
        bytesPerLine = 3 * width
        q_image = QImage(image.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        self.pixmap_item.resetTransform()
        self.pixmap_item.setPixmap(QPixmap(q_image))

        # stretch the image into normed size and set the scene position
        # important: use pixmap item and not the scene. Otherwise, a movement during in and out zooming will occur.
        self.pixmap_item.setScale(2 ** self.slide_lvl_active)
        self.pixmap_item.setPos(*self.scene_pos)

    def slide_change(self, slide_change: int):
        """
        Adds value to the slide level goal, the displayed slide level is handled internal
        :param slide_change: wanted difference to current slide level
        :type slide_change: int
        :return: /
        """
        self.slide_lvl_goal += slide_change
        self.slide_lvl_goal = max([self.slide_lvl_goal, 0])             # goal can not be less zero
        self.slide_lvl_goal = min([self.slide_lvl_goal, self.num_lvl])  # goal can not be more when max number of level

    @pyqtSlot()
    def update_image_check(self):
        """
        Checks which level can be and if unloaded areas are displayed. This function decides if a new image will be
        displayed. It goes through all level from the goal to the current one. If a slide fits completely into the view,
        it will be displayed. If no slide fits, it will stay in the current level, but checks if a corner of the view is
        outside the slide. If so, the current slide_level will be raised (prevents displaying of unloaded areas).
        :return: /
        """
        if self.scene():  # don't run code without a scene, prevents crashes
            slides = self.slide_loader.get_zoom_stack()
            view_up_left = self.scene().views()[0].mapToScene(int(0.02 * self.view_width),
                                                              int(0.02 * self.view_height))  # 2% buffer for frame
            view_low_right = self.scene().views()[0].mapToScene(int(0.98 * self.view_width),
                                                                int(0.98 * self.view_height))  # 2% buffer for frame

            for lvl in range(min(self.slide_lvl_goal, self.slide_lvl_active),
                             max(self.slide_lvl_goal, self.slide_lvl_active) + 1):
                scene_up_left_goal = slides[lvl]['position']
                scene_low_right_goal = scene_up_left_goal + self.slide_loader.slide_size[lvl] * 2 ** lvl

                # check for best slide level
                if (view_up_left.x() > scene_up_left_goal[0] and  # check if slide fits completely int the view
                    view_up_left.y() > scene_up_left_goal[1] and  # completely is the reason for use of "and"
                    view_low_right.x() < scene_low_right_goal[0] and
                    view_low_right.y() < scene_low_right_goal[1]) and \
                        lvl < self.slide_lvl_active:  # to ensure that not every time an image will be displayed
                    self.slide_lvl_active = lvl
                    self.set_image()
                    break   # if a slide fits, second check is not needed (code efficiency)

                # check for unloaded areas
                elif (view_up_left.x() < scene_up_left_goal[0] or  # check if one corner is unloaded
                      view_up_left.y() < scene_up_left_goal[1] or  # cover of all corners needs "or"
                      view_low_right.x() > scene_low_right_goal[0] or
                      view_low_right.y() > scene_low_right_goal[1]) and lvl == self.slide_lvl_active:
                    self.slide_lvl_active += 1
                    if self.slide_lvl_active >= self.num_lvl:  # check if you are already on the highest level
                        self.slide_lvl_active = self.num_lvl
                        self.set_image()
                        # Stop function, if on the highest level(no update is required
                        # most of the time, the view on the highest level will be outside the slide
                        return  # prevents emitting start_checking/stops the function

                    self.set_image()
        self.start_checking.emit()

    def wheelEvent(self, event: 'QGraphicsSceneWheelEvent'):
        """
        WheelEvent will cause a zoom. This function changes the wanted slide level according to the zoom direction.
        Also it will set the active slide level to the highest possible. Therefore, the "update_image_check" will handle
        the correct displayed slide level.
        :param event: event to initialize the function
        :type event: QGraphicsSceneWheelEvent
        :return: /
        """
        hysteresis = 1.5
        # to ensure a hysteresis (need to be larger when 1)
        # theoretically 2 is enough, but it seems to work better with 1.5
        image_pos_upleft = self.scene().views()[0].mapToScene(0, 0)
        image_pos_lowright = self.scene().views()[0].mapToScene(self.view_width, self.view_height)

        if self.view_width >= self.view_height:  # check for larger dimension
            width_image = (image_pos_lowright.x() - image_pos_upleft.x()) / (2 ** self.slide_lvl_active)
            if width_image <= self.view_width and event.delta() > 0:
                self.slide_change(int(-1))
            if width_image / hysteresis > self.view_width and event.delta() < 0:    # to ensure a hysteresis
                self.slide_change(int(+1))

        else:
            height_image = (image_pos_lowright.y() - image_pos_upleft.y()) / (2 ** self.slide_lvl_active)
            if height_image <= self.view_height and event.delta() > 0:
                self.slide_change(int(-1))
            if height_image / hysteresis > self.view_height and event.delta() < 0:  # to ensure a hysteresis
                self.slide_change(int(+1))

        self.slide_lvl_active = self.num_lvl    # set active level to highest possible
        self.start_checking.emit()  # restart the update (after pausing on highest level)

    def mouseReleaseEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """
        Adds a level after panning to prevent unloaded data
        :param event: event to initialize the function
        :type event: QGraphicsSceneMouseEvent
        :return: /
        """
        self.slide_lvl_active = min([self.slide_lvl_active + 1, self.num_lvl])
        self.set_image()

    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """
        Function needs to be implemented for other QGraphicsSceneMouseEvent.
        :param event: event to initialize the function
        :type event: QGraphicsSceneMouseEvent
        :return: /
        """
        pass

    def hoverMoveEvent(self, event: 'QGraphicsSceneHoverEvent'):
        """
        Gives the slide loader the current mouse position
        :param event: event to initialize the function
        :type event: QGraphicsSceneHoverEvent
        :return: /
        """
        mouse_scene_pos = self.mapToScene(event.pos())
        self.mouse_pos = np.array([mouse_scene_pos.x(), mouse_scene_pos.y()]).astype(int)
        self.slide_loader.mouse_pos = self.mouse_pos

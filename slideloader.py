from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Union, Dict, List
from typing_extensions import TypedDict
import numpy as np
from openslide import OpenSlide


class ZoomDict(TypedDict):
    position: np.ndarray    # pixel location of the upper left of the data
    data: np.ndarray        # row data of the image


class SlideLoader(QObject):
    update_slides = pyqtSignal()

    def __init__(self, filepath: str, width: int, height: int):
        """
        Initialization of SlideLoader
        :param filepath: path of the slide data.
        :type filepath: str
        :param width: width of the GraphicsView
        :type width: int
        :param height: height of the GraphicView
        :type height: int
        """
        super(SlideLoader, self).__init__()
        self.slide: OpenSlide = OpenSlide(filepath)
        self._slide_loader_thread = QThread()
        self.moveToThread(self._slide_loader_thread)
        self._slide_loader_thread.start()

        self.num_lvl: int = 0                           # total number of level
        self.slide_size: List[np.ndarray] = []          # list of the size of each level
        self._zoom_stack: Dict[int, ZoomDict] = {}      # stack of the images along the level under the mouse position
        self.mouse_pos: np.ndarray = np.array([0, 0])   # current mouse position
        self.old_center: np.ndarray = np.array([0, 0])  # position on the lowest level on the last update
        self.new_file: bool = True                      # flag for new fie
        self.view_width: int = width                    # width of the GraphicsView
        self.view_height: int = height                  # height of the GraphicsView
        self._stack_mutex = QMutex()                    # locker to ensure now clash between
                                                        # reading and writing the _zoom_stack
        self._updating_slides: bool = True              # flag if update is running

        self.update_slides.connect(self.updating_zoom_stack, Qt.ConnectionType.QueuedConnection)
        self.update_slide_size(width=width, height=height)
        self.updating_zoom_stack()  # call it ones to start the update

    def set_slide(self, filepath: str):
        """
        Loads a new slide
        :param filepath: path of the slide data.
        :type filepath: str
        :return: /
        """
        self.slide = OpenSlide(filepath)    # not included in constructor in case a new file os loaded

    def update_slide_size(self, width: int, height: int):
        """
        Calcuating the needed size of the different level based on the current window size. The resolution of the lower
        levels depend on the window size and not on the original one. Function has to be called after loading new data.
        :param width: width of the GraphicsView
        :type width: int
        :param height: height of the GraphicView
        :type height: int
        :return: /
        """
        self.slide_size = []
        self.num_lvl = 0
        self.view_width = width     # assigned if window size changes
        self.view_height = height   # assigned if window size changes
        size = max([self.view_width, self.view_height])

        # calculating the number of needed levels (cuts off the small slides)
        dim = 0 if self.view_width > self.view_height else 1
        for size_slide in np.array(self.slide.level_dimensions)[1:, dim]:
            if size > size_slide:
                break
            else:
                self.num_lvl += 1

        # calculate the required size for next slide to ensure the image fills the view, factor "2" as panning buffer
        resize_fac = 2 * np.array(self.slide.level_dimensions)[self.num_lvl, dim] / size
        level_dimensions = np.asarray([self.view_width, self.view_height])

        # calculate the size of each level
        for n in range(self.num_lvl, 0, -1):
            self.slide_size.append((level_dimensions * resize_fac).astype(int))

        # append the upper slide with no resize factor (to display the original size on the highest level)
        self.slide_size.append(np.asarray(self.slide.level_dimensions[self.num_lvl]).astype(int))

        self.mouse_pos = (np.asarray(self.slide.level_dimensions[0]) / 2).astype(int)
        self.old_center = self.mouse_pos
        self.new_file = True    # ensure a new stack will be load

    @pyqtSlot()
    def updating_zoom_stack(self):
        """
        The function calculates a stack of images of the respective level. Each image has an identical size , leading to
        display a smaller part of the slide with a higher resultion. To ensure a movement to the mouse position while
        zooming in, the center of each image is located along a line. This line goes through the center of the highest
        level (largest image with smallest resolution) to the mouse position on the lowest level (smallest image with
        highest resolution). Hind: Image the stack as a flipped skew pyramid with the mouse position on the top. Moving
        the mouse equals moving the top of the pyramid with a fixed bottom.
        :return: /
        """
        new_stack: Dict[int, ZoomDict] = {}  # clear stack

        # set the centers for lowest and highest level
        center_high_lvl = (np.asarray(self.slide.level_dimensions[0]) / 2).astype(int)
        center_low_lvl = self.mouse_pos

        # check if an update is necessary
        diff = np.abs(self.old_center - center_low_lvl)
        reserve = np.asarray([self.view_width, self.view_height])/2

        if self.new_file or\
           diff[0] > reserve[0] or\
           diff[1] > reserve[1]:  # check if new position will fit into current slides; ensure stack loads for new files
            # calculate the centers along a line with a geometrical distribution.
            # Caution: The absolut distance must be distributed to cover the case to zoom into the right-hand side
            distance = np.abs(center_high_lvl - center_low_lvl)
            distance[0] = 1 if distance[0] == 0 else distance[0]  # geometrical space cannot work with "0"
            distance[1] = 1 if distance[1] == 0 else distance[1]  # geometrical space cannot work with "0"

            # calculating the centers depending on the positions
            if center_low_lvl[0] <= center_high_lvl[0]:
                centers_x = center_low_lvl[0] + np.around(np.geomspace(0.1, distance[0], num=self.num_lvl+1),
                                                          decimals=1)
            else:
                centers_x = center_low_lvl[0] - np.around(np.geomspace(0.1, distance[0], num=self.num_lvl+1),
                                                          decimals=1)
            if center_low_lvl[1] <= center_high_lvl[1]:
                centers_y = center_low_lvl[1] + np.around(np.geomspace(0.1, distance[1], num=self.num_lvl+1),
                                                          decimals=1)
            else:
                centers_y = center_low_lvl[1] - np.around(np.geomspace(0.1, distance[1], num=self.num_lvl+1),
                                                          decimals=1)
            slide_centers = np.stack([centers_x, centers_y], axis=1)

            # update the stack with the calculated centers
            for slide_lvl in range(self.num_lvl + 1):
                slide_pos = (slide_centers[slide_lvl, :] - self.slide_size[slide_lvl] * 2 ** slide_lvl / 2).astype(int)
                data = np.array(self.slide.read_region(slide_pos, slide_lvl, self.slide_size[slide_lvl]).convert('RGB'))
                new_stack.update({slide_lvl: ZoomDict(position=slide_pos, data=data)})

            # override the zoom_stack with QMutexLocker to prevent parallel reading and writing
            with QMutexLocker(self._stack_mutex):
                self._zoom_stack = new_stack

            self.old_center = center_low_lvl

        self.new_file = False
        if self._updating_slides:
            self.update_slides.emit()  # use a signal for constant updating

    def get_zoom_stack(self):
        """
        Returns the current stack of slides
        :return: stack of slides
        """
        # use of QMutexLocker to prevent parallel reading and writing
        with QMutexLocker(self._stack_mutex):
            return self._zoom_stack

    def start_updating(self):
        """
        Starts updating the slides under the mouse position
        :return: /
        """
        self._updating_slides = True
        self.updating_zoom_stack()  # call it again to restart

    def stop_updating(self):
        """
        Stops the current updating of the slides under the mouse position
        :return: /
        """
        self._updating_slides = False

    def status_update(self):
        """
        Returns if the update of slides is currently running
        :return: Status updating_zoom_stack (True if active)
        """
        return self._updating_slides


from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from typing import Union, Dict, Tuple, List
from typing_extensions import TypedDict
import numpy as np
from openslide import OpenSlide
from PIL import Image


class ZoomDict(TypedDict):
    position: np.ndarray  # pixel location of the upper left of the data?
    data: np.ndarray


class SlideLoader(QObject):
    start_updating = pyqtSignal()

    def __init__(self, filepath: str, width: int, height: int):
        super(SlideLoader, self).__init__()
        self._slide_loader_thread = QThread()
        self.moveToThread(self._slide_loader_thread)
        self._slide_loader_thread.start()

        self.slide_filepath: str = None
        self.slide: OpenSlide = None
        self.num_lvl: int = None
        self.slide_size: List[np.ndarray] = []
        self.zoom_stack: Dict[int, ZoomDict] = None
        self.mouse_pos: np.ndarray = None
        self.scene_pos: np.ndarray = None
        self.slide_lvl: int = None
        self.dominate_x: bool = None
        self.old_center: np.ndarray = None
        self.new_file: bool = None
        self.view_width: int = None
        self.view_height: int = None
        self._stack_mutex = QMutex()
        self._slide_mutex = QMutex()

        self.start_updating.connect(self.set_zoom_stack, Qt.ConnectionType.QueuedConnection)
        self.set_slide(filepath)
        self.update_slide(width=width, height=height)
        self.set_zoom_stack()  # call it ones to ensure a stack is loaded

    def set_slide(self, filepath: str):
        """
        not included in constructor in case a new file os loaded
        """
        self.slide = OpenSlide(filepath)

    def update_slide(self, width: int, height: int):
        with QMutexLocker(self._slide_mutex):
            """
            check which dimension is larger
            must be separated from "set_slide" because it is also used for change of the screen size
            """
            self.slide_size = []
            self.view_width = width
            self.view_height = height
            if np.asarray(self.slide.level_dimensions[-1])[0] >= np.asarray(self.slide.level_dimensions[-1])[1]:
                self.dominate_x = True
            else:
                self.dominate_x = False
            size_slide = self.view_width if self.dominate_x else self.view_height
            self.num_lvl = 0

            """
            cut of the to small slides
            """
            dim = 0 if self.dominate_x else 1
            for i in np.array(self.slide.level_dimensions)[1:, dim]:
                if size_slide > i:
                    break
                else:
                    self.num_lvl += 1

            """
            calculate the needed size for the slides
            factor "2" as panning buffer
            factor "1.5" as current buffer for higher levels
            factor "1" currently now buffer for lower levels used
            """
            resize_fac = 2 * 1.5 * np.array(self.slide.level_dimensions)[self.num_lvl, 0] / size_slide
            level_dimensions = np.asarray([self.view_width, self.view_height])
            for n in range(self.num_lvl, 0, -1):
                self.slide_size.append((level_dimensions * resize_fac * 1 ** n).astype(int))
            self.slide_size.append(np.asarray(self.slide.level_dimensions[self.num_lvl]).astype(int))    # append the upper slide with no resize factor
            """
            just assignments
            """
            self.slide_lvl = self.num_lvl
            self.scene_pos = np.array([0, 0])
            self.mouse_pos = (np.asarray(self.slide.level_dimensions[0]) / 2).astype(int)
            self.old_center = self.mouse_pos
            self.new_file = True

    @pyqtSlot()
    def set_zoom_stack(self):
        with QMutexLocker(self._slide_mutex):
            new_stack: Dict[int, ZoomDict] = {}  # clear stack

            """
            set the centers for lowest and highest level
            """
            center_high_lvl = (np.asarray(self.slide.level_dimensions[0]) / 2).astype(int)
            center_low_lvl = self.mouse_pos

            """
            check if an update is necessary
            """
            diff = np.abs(self.old_center - center_low_lvl)
            reserve = self.slide_size[0]/2

            if self.new_file or diff[0] > reserve[0] or diff[1] > reserve[1]:  # check if new position will fit into current slides
                """
                calculate the centers along a line with a geometrical distribution.
                Caution: The absolut distance must be distributed
                """
                distance = np.abs(center_high_lvl - center_low_lvl)
                distance[0] = 1 if distance[0] == 0 else distance[0]  # geometrical space cannot work with "0"
                distance[1] = 1 if distance[1] == 0 else distance[1]  # geometrical space cannot work with "0"
                if center_low_lvl[0] <= center_high_lvl[0]:
                    centers_x = np.around(np.geomspace(0.1, distance[0], num=self.num_lvl + 1)).astype(int) + center_low_lvl[0]
                else:
                    centers_x = -np.around(np.geomspace(0.1, distance[0], num=self.num_lvl + 1)).astype(int) + center_low_lvl[0]
                if center_low_lvl[1] <= center_high_lvl[1]:
                    centers_y = np.around(np.geomspace(0.1, distance[1], num=self.num_lvl + 1)).astype(int) + center_low_lvl[1]
                else:
                    centers_y = -np.around(np.geomspace(0.1, distance[1], num=self.num_lvl + 1)).astype(int) + center_low_lvl[1]
                slide_centers = np.stack([centers_x, centers_y], axis=1)

                """
                update the stack with the calculated centers
                """
                for slide_lvl in range(self.num_lvl + 1):
                    slide_pos = (slide_centers[slide_lvl, :] - self.slide_size[slide_lvl] * 2 ** slide_lvl / 2).astype(int)
                    data = np.array(self.slide.read_region(slide_pos, slide_lvl, self.slide_size[slide_lvl]).convert('RGB'))
                    new_stack.update({slide_lvl: ZoomDict(position=slide_pos, data=data)})

                self.zoom_stack = new_stack
                self.old_center = center_low_lvl
            self.new_file = False
        self.start_updating.emit()  # use a signal for constant updating

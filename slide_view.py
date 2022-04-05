from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from typing import Union, Dict, Tuple, List
from typing_extensions import TypedDict
import numpy as np
from openslide import OpenSlide
from PIL import Image
"""
ToDo:
- move add item to constructor
- speed up loading process
- fix issue that slide moves into upper left corner when zooming out --> maybe fixed, not reconstructable
- handling of resize --> images are to small for large window sizes
"""


class ZoomDict(TypedDict):
    position: np.ndarray  # pixel location of the upper left of the data?
    data: np.ndarray


class SlideLoader(QObject):
    start_updating = pyqtSignal()

    def __init__(self, filepath: str):
        super(SlideLoader, self).__init__()
        self._slide_loader_thread = QThread()
        self.moveToThread(self._slide_loader_thread)
        self._slide_loader_thread.start()

        self.slide_filepath: str = None
        self.slide: OpenSlide = None
        self.num_lvl: int = None
        self.slide_size: List[np.ndarray] = []
        self.zoom_stack: Dict[np.ndarray, ZoomDict] = None
        self.mouse_pos: np.ndarray = None
        self.scene_pos: np.ndarray = None
        self.slide_lvl: int = None
        self.dominate_x: bool = None
        self._stack_mutex = QMutex()

        self.start_updating.connect(self.set_zoom_stack, Qt.ConnectionType.QueuedConnection)
        self.set_slide(filepath)
        self.update_slide()

    @pyqtSlot(str)
    def set_slide(self, filepath: str):
        """
        not included in constructor in case a new file os loaded
        """
        self.slide = OpenSlide(filepath)

    def update_slide(self, size_x=660, size_y=600):
        """
        check which dimension is larger
        """
        self.dominate_x = True if np.asarray(self.slide.level_dimensions[-1])[0] >= \
                                  np.asarray(self.slide.level_dimensions[-1])[1] else False
        size_slide = size_x if self.dominate_x else size_y
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
        resize_fac = 2 * 1.5 * size_slide / np.array(self.slide.level_dimensions)[self.num_lvl, 0]
        level_dimensions = np.asarray(self.slide.level_dimensions[self.num_lvl])
        for n in range(self.num_lvl, 0, -1):
            self.slide_size.append((level_dimensions * resize_fac * 1 ** n).astype(int))
        self.slide_size.append(level_dimensions.astype(int))    # append the upper slide with no resize factor
        """
        just assignments
        """
        self.slide_lvl = self.num_lvl
        self.scene_pos = np.array([0, 0])
        self.mouse_pos = (np.asarray(self.slide.level_dimensions[0])).astype(int)
        self.set_zoom_stack()  # call it ones to ensure a stack is loaded

    @pyqtSlot()
    def set_zoom_stack(self):
        new_stack: Dict[int, ZoomDict] = {}  # clear stack

        """
        set the centers for lowest and highest level
        """
        center_high_lvl = (np.asarray(self.slide.level_dimensions[0]) / 2).astype(int)
        center_low_lvl = self.mouse_pos
        center_low_lvl[0] = 1 if center_low_lvl[0] == 0 else center_low_lvl[0]  # geometrical space cannot work with "0"
        center_low_lvl[1] = 1 if center_low_lvl[1] == 0 else center_low_lvl[1]  # geometrical space cannot work with "0"

        """
        calculate the centers along a line with a geometrical distribution.
        Caution: The absolut distance must be distributed
        """
        distance = np.abs(center_high_lvl - center_low_lvl)
        centers_x = np.around(np.geomspace(0.1, distance[0], num=self.num_lvl + 1)).astype(int) + center_low_lvl[0] \
            if center_low_lvl[0] <= center_high_lvl[0] \
            else -np.around(np.geomspace(0.1, distance[0], num=self.num_lvl + 1)).astype(int) + center_low_lvl[0]
        centers_y = np.around(np.geomspace(0.1, distance[1], num=self.num_lvl + 1)).astype(int) + center_low_lvl[1] \
            if center_low_lvl[1] <= center_high_lvl[1] \
            else -np.around(np.geomspace(0.1, distance[1], num=self.num_lvl + 1)).astype(int) + center_low_lvl[1]
        slide_centers = np.stack([centers_x, centers_y], axis=1)

        """
        update the stack with the calculated centers
        """
        for slide_lvl in range(self.num_lvl + 1):
            slide_pos = (slide_centers[slide_lvl, :] - self.slide_size[slide_lvl] * 2 ** slide_lvl / 2).astype(int)
            data = np.array(self.slide.read_region(slide_pos, slide_lvl, self.slide_size[slide_lvl]).convert('RGB'))
            new_stack.update({slide_lvl: ZoomDict(position=slide_pos, data=data)})
        with QMutexLocker(self._stack_mutex):   # ensure the current stack is assigned before return the stack
            self.zoom_stack = new_stack

        self.start_updating.emit()  # use a signal for constant updating

    def get_zoom_stack(self, level: int = None):
        with QMutexLocker(self._stack_mutex):
            if level:
                return [self.zoom_stack[level]['data'].copy()]
            else:
                return [self.zoom_stack[x]['data'].copy() for x in self.zoom_stack]

    @pyqtSlot(int, int)
    def mouse_position_changed(self, mouse_x: int, mouse_y: int):
        self.mouse_pos = np.array([mouse_x, mouse_y])

    @pyqtSlot(int, int, int)
    def get_pos_update_from_scene(self, scene_pos_x: int, scene_pos_y: int, slide_lvl: int):
        self.scene_pos = np.array([scene_pos_x, scene_pos_y])
        self.slide_lvl = slide_lvl


class BaseGraphicsScene(QGraphicsScene):
    mouse_moved = pyqtSignal(int, int)
    pos_update_to_slide = pyqtSignal(int, int, int)

    def __init__(self, filepath):
        super(BaseGraphicsScene, self).__init__()
        self.pixmap_item = QGraphicsPixmapItem()  # type: QGraphicsPixmapItem

        self.slideloader: SlideLoader = None
        self.num_lvl: int = None
        self.slide_lvl: int = None
        self.scene_pos: np.ndarray = None
        self.mouse_pos: np.ndarray = None

        self.refactor_image(filepath)
        self.addItem(self.pixmap_item)

    def refactor_image(self, filepath):
        """
        used for new slides
        """
        self.slideloader = SlideLoader(filepath)
        self.mouse_moved.connect(self.slideloader.mouse_position_changed)
        self.pos_update_to_slide.connect(self.slideloader.get_pos_update_from_scene)

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
        self.pixmap_item.setScale(2 ** self.slide_lvl)
        self.pixmap_item.setPos(*self.scene_pos)
        self.send_pos_update()

    def mouse_position_changed(self, mouse_scene_pos: QPoint):
        self.mouse_pos = np.array([mouse_scene_pos.x(), mouse_scene_pos.y()]).astype(int)
        self.mouse_moved.emit(self.mouse_pos[0], self.mouse_pos[1])

    def send_pos_update(self):
        self.pos_update_to_slide.emit(int(self.scene_pos[0]), int(self.scene_pos[1]), int(self.slide_lvl))

    @pyqtSlot(int)
    def slide_change(self, slide_change: int):
        self.slide_lvl += slide_change
        if self.slide_lvl < 0:
            self.slide_lvl = 0
            pass    # no image_update if on lowest slide
        if self.slide_lvl > self.slideloader.num_lvl:
            self.slide_lvl = self.slideloader.num_lvl
            pass    # no image_update if on highest slide
        self.set_image()


class GraphicsView(QGraphicsView):
    slide_change = pyqtSignal(int)
    start_checking = pyqtSignal()

    def __init__(self, *args):
        super(GraphicsView, self).__init__(*args)
        self.setBackgroundBrush(QBrush(QColor("r")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self.slide_change.connect(self.scene().slide_change)
        self.start_checking.connect(self.update_check, Qt.ConnectionType.QueuedConnection)

        self.setMouseTracking(True)
        self._pan_start: bool = False
        self._panning: bool = False

        self.scene().set_image()
        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.update_check()     # called ones to start


class GraphicsHandle(QGraphicsObject):

    def __init__(self, *__args):
        super(QGraphicsObject, self).__init__(*__args)
        self.setParent(GraphicsView)
        self.setParent(BaseGraphicsScene)

        self.slide_change.connect(self.scene().slide_change)
        self.start_checking.connect(self.update_check, Qt.ConnectionType.QueuedConnection)

        self.setMouseTracking(True)
        self._pan_start: bool = False
        self._panning: bool = False

        """
        update
        """
        self.scene().set_image()

        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.update_check()     # called ones to start

    """
    update
    """
    def fitInView(self, *__args):
        if self.scene():
            super(GraphicsView, self).fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        pass

    def wheelEvent(self, event: QWheelEvent):
        """
        scales the image and moves into the mouse position
        """
        oldPos = self.mapToScene(event.position().toPoint())
        scale_factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(scale_factor, scale_factor)
        newPos = self.mapToScene(event.position().toPoint())
        move = newPos - oldPos
        self.translate(move.x(), move.y())

        """
        Checks if current or next lower image resolution is high enough for the window size
        """
        image_pos_upleft = self.mapToScene(0, 0)
        image_pos_lowright = self.mapToScene(self.viewport().width(), self.viewport().height())
        distance = (image_pos_lowright.x() - image_pos_upleft.x()) / (2 ** self.scene().slide_lvl) \
            if self.scene().slideloader.dominate_x \
            else (image_pos_lowright.y() - image_pos_upleft.y()) / (2 ** self.scene().slide_lvl)  # check for larger dimension
        if distance <= self.viewport().width():
            self.slide_change.emit(int(-1))
        if distance / 2 > self.viewport().width():  # the resolution difference between two slides is "2"
            self.slide_change.emit(int(+1))
        print(f'Slide level: {self.scene().slide_lvl}')

    def resizeEvent(self, event: QResizeEvent):
        """
        currently just fits the view after resizing
        ToDo: fix the problem with large window sizes. If started with a small window size and change into a large one, the images are to small to fit
        """
        # self.scene().slideloader.update_slide(self.width(), self.height())
        # self.scene().set_image()
        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = True
            self._pan_start = self.mapToScene(event.pos())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            self.scene().set_image()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            new_pos = self.mapToScene(event.pos())
            move = new_pos - self._pan_start
            self.translate(move.x(), move.y())
            self._pan_start = self.mapToScene(event.pos())

        if hasattr(self.scene(), "mouse_position_changed"):
            self.scene().mouse_position_changed(self.mapToScene(event.pos()))

    @pyqtSlot()
    def update_check(self):
        image_pos_upleft = self.mapToScene(0, 0)
        image_pos_lowright = self.mapToScene(self.viewport().width(), self.viewport().height())

        size = (self.scene().slideloader.slide_size[self.scene().slide_lvl] * 2 ** self.scene().slide_lvl)
        scene_pos_upleft = self.scene().scene_pos
        scene_pos_lowright = scene_pos_upleft + size

        if image_pos_upleft.x() < scene_pos_upleft[0] or image_pos_upleft.y() < scene_pos_upleft[1] or \
                image_pos_lowright.x() > scene_pos_lowright[0] or image_pos_lowright.y() > scene_pos_lowright[1]:
            self.scene().set_image()
        self.start_checking.emit()

def show_reference(filepath):
    test_slide = OpenSlide(filepath)
    reference = np.asarray(test_slide.read_region((0, 0), 6, np.array([440, 400])).convert('RGB'))
    img = Image.fromarray(reference)
    img.show()


if __name__ == '__main__':
    app = QApplication(['test'])
    file = r'C:\Users\danie\OneDrive\Dokumente\GitHub\D-Schiller\Implementation\A76_19_1.tiff'
    scene = BaseGraphicsScene(filepath=file)
    viewer = GraphicsView(scene)
    viewer.show()
    app.exec()

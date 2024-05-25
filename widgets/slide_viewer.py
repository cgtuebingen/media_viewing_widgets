import os
import sys
import numpy as np

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, Signal, QPoint, QRectF, Slot, QThread, QTimer
from PySide6.QtGui import QPainter, Qt, QPixmap, QResizeEvent, QWheelEvent, QMouseEvent, QTransform
from PySide6.QtWidgets import QGraphicsView, QGraphicsPixmapItem

if sys.platform.startswith("win"):
    openslide_path = os.path.abspath("./openslide/bin")
    os.add_dll_directory(openslide_path)
from openslide import OpenSlide


class SlideView(QGraphicsView):
    """
    The SlideView class is a widget that displays a whole slide image (WSI) using the OpenSlide library.
    It is possible to zoom in and out, pan and annotate the image.
    """
    sendPixmap = Signal(QPixmap)
    pixmapFinished = Signal()

    def __init__(self, *args):
        super().__init__(*args)

        # Configuration of the QGraphicsView
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setMouseTracking(True)

        # State Booleans
        self.annotationMode = False  # Annotation mode active
        self.updating = False  # Image is currently updating
        self.panning = False  # Image can be panned
        self.moved = False  # Image has been moved
        self.zoomed = True  # Image has been zoomed
        self.zoom_finished = True  # Zoom operation is finished

        # Slide and Filepath
        self.slide = None  # OpenSlide object
        self.filepath = None  # Path to the slide

        # Viewport Dimensions
        self.width = self.frameRect().width()
        self.height = self.frameRect().height()

        # Zoom Logic
        self.cur_downsample = 0.0  # Current global zoom
        self.max_downsample = 0.0  # Maximum zoom out
        self.cur_level_zoom = 0.0  # Relative zoom of current level
        self.level_downsamples = {}  # Lowest global zoom for all levels
        self.cur_level = 0  # Current zoom level
        self.zoom_offset = QPointF()  # Offset for zoom when setting the new anchor point
        self.zoomed_factor = 1  # Zoom factor when setting the new anchor point

        # Display Logic
        self.fused_image = Image.Image()  # Image container to store the image patches too
        self.pixmap = QPixmap()  # Pixmap that stores the current image
        self.anchor_point = QPoint()  # Anchor point for the image
        self.pixmap_compensation = QPointF()  # Compensation to move image after creation
        self.image_patches = {}  # Storage for image patches

        # Threading Logic
        self.max_threads = 16  # Maximum number of threads
        self.sqrt_thread_count = 4  # Square root of thread count
        self.image_thread = None  # Thread for image processing

        # Signal Connections
        self.pixmapFinished.connect(self.set_pixmap)  # sends finished pixmap

    def load_slide(self, filepath: str, width: int = None, height: int = None):
        """
        Loads the currently selected slide and sets up all other parameters needed to display the image.
        :param filepath: path of the _slide data. The data type is based on the OpenSlide library and can handle:
                         Aperio (.svs, .tif), Hamamatsu (.vms, .vmu, .ndpi), Leica (.scn), MIRAX (.mrxs),
                         Philips (.tiff), Sakura (.svslide), Trestle (.tif), Ventana (.bif, .tif),
                         Generic tiled TIFF (.tif) (see https://openslide.org)
        :type filepath: str
        :param width: width of the GraphicsView
        :type width: int
        :param height: height of the GraphicView
        :type height: int
        :return: /
        """
        # TODO: Temporary solution for saving the zoom and movement of the current wsi slide.
        #  This will not save the zoom if the user switches to any other whole slide image.
        if self.filepath and self.filepath == filepath:
            self.update_pixmap()
            self.sendPixmap.emit(self.pixmap)
            return

        # Setting slide and filepath
        self.slide = OpenSlide(filepath)
        self.filepath = filepath

        # If there are no width and height given at the initialization, set the width and height of the Viewport
        if not width or not height:
            self.width = self.frameRect().width()
            self.height = self.frameRect().height()

        # Calculate the size of the scene (double the image size)
        bottom_right = QPointF(self.slide.dimensions[0], self.slide.dimensions[1])
        scene_rect = QRectF(-bottom_right, bottom_right)
        self.setSceneRect(scene_rect)

        # Initialize the pixmap and the fused image as 4 times the size of the Viewport
        self.fused_image = Image.new('RGBA', (self.width * 4, self.height * 4))
        self.pixmap = QPixmap(self.width * 4, self.height * 4)

        # Set Zoom and Level Parameters:
        # set all downsamples for each level
        self.level_downsamples = [self.slide.level_downsamples[level] for level in range(self.slide.level_count)]
        # set the maximum downsample (global zoom out) and the current downsample
        self.max_downsample = self.cur_downsample = max(self.slide.level_dimensions[0][0] / self.width,
                                                        self.slide.level_dimensions[0][1] / self.height)
        # set the best level for the current downsample (zoom)
        self.cur_level = self.slide.get_best_level_for_downsample(self.max_downsample)
        # set the relative zoom of the current level
        self.cur_level_zoom = self.cur_downsample / self.level_downsamples[self.cur_level]
        # Set the anchor point to the top left corner of the viewport and to (0,0) at the lowest level
        self.anchor_point = QPoint(0, 0)

        # Initialize storage for the image patches
        self.image_patches = [QPixmap(self.width, self.height) for _ in range(self.max_threads)]
        self.image_patches = np.array(self.image_patches)
        self.image_patches = self.image_patches.reshape([self.sqrt_thread_count, self.sqrt_thread_count])

        # Set zoomed to true to update the whole pixmap (all patches)
        self.zoomed = True
        self.update_pixmap()

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        # Set the correct scale and offset for the displayed image
        self.scale(1 / self.cur_level_zoom, 1 / self.cur_level_zoom)
        self.translate(-self.width, -self.height)

    def update_pixmap(self):
        """
        This method handles the updated of the pixmap.
        If there is nothing to updated, this method will do nothing.
        If there are patches to update, the method will launch an asynchronous thread to update the pixmap.
        :return: /
        """
        # Check if the image is currently being updated
        if not self.updating:
            new_patches = self.check_for_new_patches()

            if any(new_patches):
                self.updating = True

                # Resetting width and height
                self.width = self.frameRect().width()
                self.height = self.frameRect().height()

                # Setting the current patch width and height
                patch_width = int(self.width)
                patch_height = int(self.height)
                # Setting the current patch width and height on level 0
                patch_width_slide = int(self.get_cur_patch_width_slide())
                patch_height_slide = int(self.get_cur_patch_height_slide())

                # Calculate the upper left corner of the pixmap on slide level 0
                offset_anchor_point = self.anchor_point - QPoint(patch_width_slide, patch_height_slide)
                # Setting the fused_image height and width
                self.fused_image = Image.new('RGBA', (self.width * 4, self.height * 4))

                # Creating a new thread to load the patches asynchronously
                # Giving it all the parameters it needs to create the patches correctly
                self.image_thread = ImageBlockWrapper(offset_anchor_point=offset_anchor_point,
                                                      block_width=patch_width,
                                                      block_height=patch_height,
                                                      block_width_slide=patch_width_slide,
                                                      block_height_slide=patch_height_slide,
                                                      sqrt_threads=self.sqrt_thread_count,
                                                      generate_new=new_patches,
                                                      max_threads=self.max_threads,
                                                      slide=self.slide,
                                                      cur_level=self.cur_level,
                                                      image_patches=self.image_patches,
                                                      fused_image=self.fused_image)
                self.image_thread.finished.connect(self.set_pixmap)
                self.image_thread.start()

    def check_for_new_patches(self) -> list[bool]:
        """
        This method checks if new patches need to be loaded.
        :return: A list of booleans
        """
        if self.zoomed:
            # If zoomed is set to true all patches will be reloaded.
            self.zoomed = False
            return [True for _ in range(self.max_threads)]
        else:
            grid_width_slide = self.get_cur_patch_width_slide()
            grid_height_slide = self.get_cur_patch_height_slide()

            # calculate current position of the upper left corner of the viewport
            int_upper_left = QPointF(self.viewportTransform().m31() / self.viewportTransform().m11(),
                                     self.viewportTransform().m32() / self.viewportTransform().m22()).toPoint()

            new_patches = [False for _ in range(self.max_threads)]

            # Check if the image was moved. If the image was moved but the zoom is not finished, this will also be false
            if not self.moved:
                return new_patches

            # Checks if the image was moved over the threshold to the right
            if int_upper_left.x() < - 2 * self.width:
                new_patches[3] = True
                new_patches[7] = True
                new_patches[11] = True
                new_patches[15] = True
                self.image_patches = self.efficient_roll(self.image_patches, -1, axis=0)
                self.anchor_point += QPoint(grid_width_slide, 0)
                self.pixmap_compensation.setX(self.pixmap_compensation.x() + self.width)

            # Checks if the image was moved over the threshold to the left
            if int_upper_left.x() > - self.width:
                new_patches[0] = True
                new_patches[4] = True
                new_patches[8] = True
                new_patches[12] = True
                self.image_patches = self.efficient_roll(self.image_patches, 1, axis=0)
                self.anchor_point -= QPoint(grid_width_slide, 0)
                self.pixmap_compensation.setX(self.pixmap_compensation.x() - self.width)

            # Checks if the image was moved over the threshold below
            if int_upper_left.y() < - 2 * self.height:
                new_patches[12] = True
                new_patches[13] = True
                new_patches[14] = True
                new_patches[15] = True
                self.image_patches = self.efficient_roll(self.image_patches, -1, axis=1)
                self.anchor_point += QPoint(0, grid_height_slide)
                self.pixmap_compensation.setY(self.pixmap_compensation.y() + self.height)

            # Checks if the image was moved over the threshold above
            if int_upper_left.y() > - self.height:
                new_patches[0] = True
                new_patches[1] = True
                new_patches[2] = True
                new_patches[3] = True
                self.image_patches = self.efficient_roll(self.image_patches, 1, axis=1)
                self.anchor_point -= QPoint(0, grid_height_slide)
                self.pixmap_compensation.setY(self.pixmap_compensation.y() - self.height)

        return new_patches

    @staticmethod
    def efficient_roll(arr: np._typing.NDArray, direction: int, axis: int) -> np._typing.NDArray | Exception:
        """
        This is a function that mimics the behavior of the numpy roll function,
        since the original numpy roll function is inefficient.
        :param arr: This is the array to be rolled
        :type arr: Numpy Array
        :param direction: This is the direction of which the array is to be rolled in
        :type direction: Integer
        :param axis: This is the axis of the roll
        :type axis: Integer
        :return: The rolled array
        """
        width, height = arr.shape[:2]
        if axis == 0:
            if direction == -1:
                return np.concatenate((arr[1:width], arr[0:1]), axis=0)
            if direction == 1:
                return np.concatenate((arr[width - 1:width], arr[:width - 1]), axis=0)
        if axis == 1:
            if direction == -1:
                return np.concatenate((arr[:, 1:height], arr[:, 0:1]), axis=1)
            if direction == 1:
                return np.concatenate((arr[:, height - 1:height], arr[:, :height - 1]), axis=1)
        return Exception(f'An incorrect axis: {axis} or an incorrect direction: {direction} was chosen!')

    def setAnnotationMode(self, b: bool):
        """
        This method sets the annotation Mode of the Slide Widget
        :param b: Boolean to set the annotation mode to
        :return: /
        """
        self.annotationMode = b

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Updates the pixmap of the widget if it is resized.
        :param event: event to initialize the function
        :return: /
        """
        if self.slide:
            self.zoomed = True
            self.update_pixmap()

    @Slot(QWheelEvent)
    def wheelEvent(self, event: QWheelEvent):
        """
        Zooming event in context to the mouse position.
        :param event: event to initialize the function
        :type event: QWheelEvent
        :return: /
        """
        # Setting the Anchor to the mouse position, so that it zooms towards the mouse
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # This signals the widget, that there is no moving updated allowed while this is loading
        self.moved = False
        # Calculate the scaling factor according to if the user zoomed in or out
        scale_factor = 1.0 / 1.1 if event.angleDelta().y() > 0 else 1.1
        inv_scale_factor = 1.0 / scale_factor
        # Scaling the global zoom
        new_downsample = self.cur_downsample * scale_factor

        # Checks if the lower or upper bound was reached
        if new_downsample > self.max_downsample or new_downsample < 0.3:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
            return

        # Scales the Viewport
        self.scale(inv_scale_factor, inv_scale_factor)
        # Set the current global zoom
        self.cur_downsample = new_downsample

        # Checks if the level needs to be changed
        self.level_change_check()

        # Set the anchor back to no anchor and update pixmap
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.update_pixmap()

    def level_change_check(self):
        """
        This checks if the level changed and prepares the Widget for a level change if the level changed.
        :return: /
        """
        # Checks if the level has changed and if the current zoom is finished
        if self.cur_level != self.slide.get_best_level_for_downsample(self.cur_downsample) and self.zoom_finished:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.zoomed = True
            # Get the current level difference
            level_diff = self.cur_level - self.slide.get_best_level_for_downsample(self.cur_downsample)

            # This if statement checks, whether the user is zooming in our out.
            if self.cur_level > self.slide.get_best_level_for_downsample(self.cur_downsample):
                # When zooming in, we need to check for the level difference, since we could zoom over multiple
                # levels at once. The current offset from the old anchor point to the new one is the distance on the
                # current level, time 2 to the power of the level difference.
                # TODO: This assumes that the downsample for each level is 2.
                #  This should be changed to an arbitrary downsample.
                self.zoomed_factor = 2 ** level_diff
                back_scale = (0.5 * self.zoomed_factor) / self.viewportTransform().m11()
            else:
                # The same principal applies here, only that the distance is halved for each level difference.
                self.zoomed_factor = 0.5 ** (-level_diff)
                back_scale = self.zoomed_factor / self.viewportTransform().m11()

            # Zooming to the threshold
            self.scale(back_scale, back_scale)
            # Calculating the vector from the old anchor point to the current top left corner of the viewport
            self.zoom_offset = QPoint(
                -(int(self.viewportTransform().m31() / self.viewportTransform().m11()) + self.width),
                -(int(self.viewportTransform().m32() / self.viewportTransform().m11()) + self.height))
            # Setting the new anchorpoint (on slide level 0)
            self.anchor_point = self.anchor_point + self.zoom_offset * self.level_downsamples[self.cur_level]
            # Zooming back to the current zoom
            self.scale(1 / back_scale, 1 / back_scale)

            # Calculating the current level
            self.cur_level = self.slide.get_best_level_for_downsample(self.cur_downsample)
            # Preparing the widget for the calculation of the new Pixmap
            self.zoom_finished = False
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

    @Slot(QPixmap)
    def set_pixmap(self, result: QPixmap):
        """
        This method sets the newly generated pixmap as the current pixmap.
        :param result: Newly generated pixmap
        :return: /
        """
        self.pixmap = result
        # Sends the new pixmap to the display widget
        self.sendPixmap.emit(self.pixmap)

        # Setting the current anchor to no anchor
        old_anchor_mode = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

        # Checks if the current pixmap is a zoomed pixmap
        if not self.zoom_finished:
            self.zoom_adjustment()

        # Applies the translation if the pixmap was moved
        self.translate(self.pixmap_compensation.x(), self.pixmap_compensation.y())

        self.setTransformationAnchor(old_anchor_mode)
        self.pixmap_compensation = QPointF(0, 0)
        self.updating = False
        if not self.zoom_finished:
            self.zoom_finished = True
        self.moved = False

        # Check if the level has to be changed
        self.level_change_check()
        # Check if the pixmap needs to be updated
        self.update_pixmap()

    def zoom_adjustment(self):
        """
        This method calculates the adjustment that needs to be applied, if the new pixmap is a zoomed pixmap.
        This means, that the method needs to be executed, when the level changed to synchronise between levels.
        :return: /
        """
        # Ensure that the anchor is not set
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

        # Calculate the current offset to the top left corner of the pixmap
        current_width = self.viewportTransform().m31() / self.viewportTransform().m11()
        current_height = self.viewportTransform().m32() / self.viewportTransform().m22()

        # This calculates the current local scale for the level of the newly generated slide
        scale = self.level_downsamples[self.cur_level] / self.cur_downsample

        # The following code sets the new transformation,
        # so that the pixmap can be synchronized with the previous pixmap
        self.resetTransform()
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)

        # The new width and height are calculated based on the current width/height, the previously calculated offset
        # and how many levels where zoomed.
        new_width = (-self.width + (current_width + self.width + self.zoom_offset.x()) * self.zoomed_factor) * scale
        new_height = (-self.height + (current_height + self.height + self.zoom_offset.y()) * self.zoomed_factor) * scale
        self.setTransform(QTransform(scale, 0, 0,
                                     0, scale, 0,
                                     new_width, new_height, 1.0))

    @Slot(QMouseEvent)
    def mousePressEvent(self, event: QMouseEvent):
        """
        Enables panning of the image
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if event.button() == Qt.MouseButton.LeftButton and not self.annotationMode:
            self.panning = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        super().mousePressEvent(event)

    @Slot(QMouseEvent)
    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Disables panning of the image
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if event.button() == Qt.MouseButton.LeftButton and not self.annotationMode:
            self.panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        super().mouseReleaseEvent(event)

    @Slot(QMouseEvent)
    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Realizes panning, if activated
        :param event: event to initialize the function
        :type event: QMouseEvent
        :return: /
        """
        if self.panning and not self.annotationMode:
            self.update_pixmap()
            if self.zoom_finished:
                self.moved = True
        super().mouseMoveEvent(event)

    def get_cur_patch_width_slide(self):
        """
        Utility method to calculate the current width of a patch given by the current level
        :return: zoomed patch width
        """
        return int(self.width * self.level_downsamples[self.cur_level])

    def get_cur_patch_height_slide(self):
        """
        Utility method to calculate the current height of a patch given by the current level
        :return: zoomed patch height
        """
        return int(self.height * self.level_downsamples[self.cur_level])

    def get_top_left_coords(self):
        """
        This Method returns the top left corner of the viewport in slide coordinates
        :return: Top left corner of viewport in slide coordinates
        """
        offset_to_anchor = QPoint(-int(self.viewportTransform().m31() / self.viewportTransform().m11() + self.width),
                                  -int(self.viewportTransform().m32() / self.viewportTransform().m22() + self.height))
        return self.anchor_point + offset_to_anchor


class ImageBlockWrapper(QThread):
    """
    This is a thread class, that calculates the next Pixmap.
    """
    finished = Signal(QPixmap)

    def __init__(self, offset_anchor_point: QPoint, block_width: int, block_height: int, block_width_slide: int,
                 block_height_slide: int, sqrt_threads: int, generate_new: list[bool], max_threads: int,
                 slide: OpenSlide, cur_level: int, image_patches: dict, fused_image: Image.Image):
        super().__init__()
        # This is the anchorpoint but offset to the top left of the pixmap in slide coordinates
        self.offset_anchor_point = offset_anchor_point
        # This is the width of one block (patch) in viewport size
        self.block_width = block_width
        # This is the height of one block in viewport size
        self.block_height = block_height
        # This is the width of one block in slide size
        self.block_width_slide = block_width_slide
        # This is the height of one block in slide size
        self.block_height_slide = block_height_slide
        # This is the number of threads used per row or column
        self.sqrt_threads = sqrt_threads
        # This is a list of booleans, that determines which blocks need to be reloaded
        self.generate_new = generate_new
        # This is the number of threads used overall
        self.max_threads = max_threads
        # This is the slide that is extracted from
        self.slide = slide
        # This is the current level
        self.cur_level = cur_level
        # This is the storage for the current image patches
        self.image_patches = image_patches
        # This is the storage of the resulting image
        self.fused_image = fused_image

    def run(self):
        """
        Generated the new Pixmap
        :return: /
        """
        # Initialize all threads
        thread_list = [ImageBlockWorker(block_index=i,
                                        offset_anchor_point=self.offset_anchor_point,
                                        block_width=self.block_width,
                                        block_height=self.block_height,
                                        block_width_slide=self.block_width_slide,
                                        block_height_slide=self.block_height_slide,
                                        sqrt_threads=self.sqrt_threads,
                                        generate_new=self.generate_new[i],
                                        slide=self.slide,
                                        cur_level=self.cur_level,
                                        image_patches=self.image_patches,
                                        fused_image=self.fused_image) for i in
                       range(self.max_threads)]
        # Start all threads
        [thread.start() for thread in thread_list]
        # Wait for all threads
        [thread.wait() for thread in thread_list]

        # Generate a pixmap from the resulting image
        pixmap = QPixmap.fromImage(ImageQt(self.fused_image))
        # Send the pixmap to the main thread
        self.finished.emit(pixmap)


class ImageBlockWorker(QThread):
    """
    This is a helper thread class, the generated blocks (patches) of the to be generated image.
    """
    finished = Signal(QPainter)

    def __init__(self, block_index: int, offset_anchor_point: QPointF, block_width: int, block_height: int,
                 block_width_slide: int, block_height_slide: int, sqrt_threads: int, generate_new: bool,
                 slide: OpenSlide, cur_level: int, image_patches: dict, fused_image: Image.Image):
        super().__init__()
        # The index of the current block
        self.block_index = block_index
        # Offset anchor point
        self.offset_anchor_point = offset_anchor_point
        # Block width in viewport size
        self.block_width = block_width
        # Block height in viewport size
        self.block_height = block_height
        # Block width in slide size
        self.block_width_slide = block_width_slide
        # Block height in slide size
        self.block_height_slide = block_height_slide
        # Number of threads per row or column
        self.sqrt_threads = sqrt_threads
        # Boolean to check if this patch needs to be generated new
        self.generate_new = generate_new
        # Slide from which the block is extracted
        self.slide = slide
        # The current level
        self.cur_level = cur_level
        # Storage for the blocks
        self.image_patches = image_patches
        # Resulting image storage
        self.fused_image = fused_image

    def run(self):
        """
        Runs the method that generated the new patch.
        :return: /
        """
        self.process_image_block(self.block_index, self.offset_anchor_point, self.block_width,
                                 self.block_height, self.block_width_slide, self.block_height_slide,
                                 self.sqrt_threads, self.generate_new)

    def process_image_block(self, block_index: int, offset_anchor_point: QPointF, block_width: int, block_height: int,
                            block_width_slide: int, block_height_slide: int, sqrt_threads: int, generate_new: bool):
        """
        This method processes each block of the image.
        The number of blocks is determined by the max number of threads.

        :param block_index: The index of the block processed by the thread
        :param offset_anchor_point: The offset anchor point gives the upper left corner of the pixmap
        :param block_width: Describes the width of the current block in viewport coordinates
        :param block_height: Describes the height of the current block in viewport coordinates
        :param block_width_slide: Describes the width of the current block in slide coordinates
        :param block_height_slide: Describes the height of the current block in slide coordinates
        :param sqrt_threads: The square root of max threads, since the image is a rectangle
        :param generate_new: This is a boolean that checks if the current patch should be newly generated
        :return: /
        """
        # Calculate the indices of the current block
        idx_width = block_index % sqrt_threads
        idx_height = block_index // sqrt_threads

        # Calculate the current blocks upper left corner local coordinates on level 0
        block_location = (
            idx_width * block_width_slide,
            idx_height * block_height_slide
        )

        # Check if the block needs to be generated
        if generate_new:
            # Read the block from the slide object
            image = self.slide.read_region(
                (int(offset_anchor_point.x() + block_location[0]), int(offset_anchor_point.y() + block_location[1])),
                self.cur_level,
                (block_width, block_height)
            )

            # Store the new block
            self.image_patches[idx_width, idx_height] = image

        # Paste the new block into the image
        self.fused_image.paste(self.image_patches[idx_width, idx_height],
                               (idx_width * block_width, idx_height * block_height))

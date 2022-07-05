from PyQt6.QtWidgets import *
from media_viewing_widgets import VideoPlayer


if __name__ == '__main__':
    app = QApplication(["test"])
    vid = VideoPlayer()
    vid.frame_grabbed.connect(lambda x, t: print(f'got frame at time {t}'))
    vid.set_video(QFileDialog().getOpenFileName()[0])
    vid.show()
    vid.play()
    app.exec()

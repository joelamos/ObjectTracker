import sys
import cv2.cv as cv, cv2
from PyQt4.Qt import *
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
import time

def numpyArrayToQImage(array):
    if array != None:
        height, width, bytesPerComponent = array.shape
        bytesPerLine = bytesPerComponent * width;
    
        # Convert to RGB for QImage.
        cv2.cvtColor(array, cv.CV_BGR2RGB, array)

        return QImage(array.data, width, height, bytesPerLine, QImage.Format_RGB888)
    return None

def timeString(seconds):
    # If seconds is a number
    if isinstance(seconds, (int, long, float)):
        seconds = int(seconds)
        minutes = int(seconds // 60)
        remainingSeconds = int(seconds % 60)

        return str(minutes) + ':' + (str(remainingSeconds) if remainingSeconds >= 10 else '0' + str(remainingSeconds))
    else:
        return 'NaN'

def drawHoughCircles(frame):
    grayFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurredFrame = cv2.medianBlur(grayFrame, 3)
    circles = cv2.HoughCircles(blurredFrame, cv.CV_HOUGH_GRADIENT, 1, 30, param1=50, param2=30, minRadius=30, maxRadius=35)

    # If any circles found, draw them on top of the original image
    if circles is not None: 
        for i in circles[0]:  # We are only interested in the first circle
            cv2.circle(frame, (i[0], i[1]), i[2], (255, 0, 0), 1)  # Options: (H,V),Radius,(B,G,R),Thickness(-1=fill)
            cv2.circle(frame, (i[0], i[1]), 3, (0, 255, 0), -1)  # Options: (H,V),Radius,(B,G,R),Thickness(-1=fill)

def iconsEqual(icon1, icon2):
    image1 = icon1.pixmap(30).toImage()
    image2 = icon2.pixmap(30).toImage()
    return image1 == image2

class VideoThread(QThread):
    frameProcessed = pyqtSignal(QImage)
    videoEnded = pyqtSignal()

    def __init__(self, video, videoLabel, speedMultiplier):
        QThread.__init__(self)
        self.video = video
        self.fps = self.video.get(cv.CV_CAP_PROP_FPS)
        self.frameCount = self.video.get(cv.CV_CAP_PROP_FRAME_COUNT)
        self.totalSeconds = self.frameCount / self.fps
        self.startingSecond = 0
        self.videoLabel = videoLabel
        self.speedMultiplier = speedMultiplier
        self.lastFrameReturn = 0
        self.stop = False

    def getFrame(self, frameNumber):
        # We limit how often this method is allowed to fetch a frame
        if self.lastFrameReturn == 0 or time.clock() - self.lastFrameReturn > .05:
            self.video.set(cv.CV_CAP_PROP_POS_FRAMES, frameNumber)
            self.lastFrameReturn = time.clock()
            numpyImage = self.video.read()[1]
            time.sleep(.01)
            drawHoughCircles(numpyImage)
            return numpyArrayToQImage(numpyImage)
        else:
            return None

    def run(self):
        self.stop = False
        clockAtStart = time.clock()

        while not self.stop:
            runtime = self.startingSecond + ((time.clock() - clockAtStart) * self.speedMultiplier)
            currentFrame = int(runtime * self.fps)

            if currentFrame < self.frameCount - 1:
                self.video.set(cv.CV_CAP_PROP_POS_FRAMES, currentFrame)
                frame = self.video.read()[1]
                drawHoughCircles(frame)
                self.frameProcessed.emit(numpyArrayToQImage(frame))
                time.sleep(.02)
            else:  # In case of high speed multipliers, move video to end
                self.video.set(cv.CV_CAP_PROP_POS_FRAMES, self.frameCount - 1)
                frame = self.video.read()[1]
                drawHoughCircles(frame)
                self.frameProcessed.emit(numpyArrayToQImage(frame))
                time.sleep(.02)
                self.videoEnded.emit()
                break

class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        self.playIcon = QIcon('images/play.png')
        self.pauseIcon = QIcon('images/pause.png')
        self.replayIcon = QIcon('images/replay.png')
        self.playing = False
        self.__initUI()

    def __initUI(self):
        self.setGeometry(300, 300, 500, 375)
        self.setMinimumHeight(250)
        self.setWindowTitle('Object Tracker')
        self.setWindowIcon(QIcon('images/window_icon.png'))
        self.__createWidgets()
        self.__addWidgets()

    def setNewVideo(self):
        if hasattr(self, 'videoThread'):
            self.stopVideo()
        self.video = cv2.VideoCapture(unicode(QFileDialog.getOpenFileName(self, "Open video").toUtf8(), encoding="UTF-8"))
        self.videoThread = VideoThread(self.video, self.videoLabel, 1)
        self.videoThread.frameProcessed.connect(self.__updateVideoLabel)
        self.videoThread.frameProcessed.connect(self.__updateSlider)
        self.videoThread.videoEnded.connect(self.__onVideoEnded)
        self.slider.setMaximum(self.video.get(cv.CV_CAP_PROP_FRAME_COUNT) - 1)
        self.playVideoFrom(0)

    def playVideoFrom(self, frame):
        self.stopVideo(icon=self.pauseIcon)
        self.videoThread.startingSecond = frame / self.videoThread.fps
        self.videoThread.start()
        self.setPlaying(True)

    def stopVideo(self, icon=None):
        self.setPlaying(False, icon)
        self.videoThread.stop = True
        self.videoThread.wait()

    def __createWidgets(self):
        self.__populateMenuBar()
        self.__createButtons()
        self.slider = VideoSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.valueChanged.connect(self.__onSliderValueChanged)
        self.videoLabel = VideoLabel()
        #labelClickFilter = LabelClickFilter(self)
        #self.videoLabel.installEventFilter(labelClickFilter)
        #labelClickFilter.videoLabelClicked.connect(self.playButton.click)
        self.videoLabel.setStyleSheet('background-color : black;');
        self.timeLabel = QLabel('Time: 0:00 / 0:00')
        self.frameLabel = QLabel('Frames: 0 / 0')

    def __populateMenuBar(self):
        self.menuBar = self.menuBar()
        fileMenu = QMenu('File', self)
        openAction = QAction('Open video...', self)
        openAction.setShortcut('Ctrl+O')
        openAction.triggered.connect(self.setNewVideo)

        fileMenu.addAction(openAction)
        self.menuBar.addMenu(fileMenu)
        self.menuBar.addMenu(QMenu("Settings", self))

    def __createButtons(self):
        self.firstFrameButton = VideoControlButton(30, QIcon('images/first_frame.png'))
        self.jumpBackwardButton = VideoControlButton(30, QIcon('images/backward_frame.png'))
        self.playButton = VideoControlButton(38, self.playIcon)
        self.jumpForwardButton = VideoControlButton(30, QIcon('images/forward_frame.png'))
        self.lastFrameButton = VideoControlButton(30, QIcon('images/last_frame.png'))
        self.firstFrameButton.clicked.connect(self.__onFirstFramePressed)
        self.jumpBackwardButton.clicked.connect(self.__onJumpBackwardPressed)
        self.playButton.clicked.connect(self.__onPlayPressed)
        self.jumpForwardButton.clicked.connect(self.__onJumpForwardPressed)
        self.lastFrameButton.clicked.connect(self.__onLastFramePressed)

    def __addWidgets(self):
        mainLayout = QVBoxLayout()
        controlsLayout = QHBoxLayout()
        controlsLayout.setContentsMargins(100, 0, 100, 0)

        controlsLayout.addStretch()
        controlsLayout.addWidget(self.firstFrameButton)
        controlsLayout.addWidget(self.jumpBackwardButton)
        controlsLayout.addWidget(self.playButton)
        controlsLayout.addWidget(self.jumpForwardButton)
        controlsLayout.addWidget(self.lastFrameButton)
        controlsLayout.addStretch()

        mainLayout.addWidget(self.videoLabel, 1)
        mainLayout.addWidget(self.slider)
        mainLayout.addWidget(self.timeLabel)
        mainLayout.addWidget(self.frameLabel)
        mainLayout.addLayout(controlsLayout)

        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)

        centralWidget.setLayout(mainLayout)

    def setPlaying(self, playing, icon=None):
        self.playing = playing
        if icon is None:
            self.playButton.setIcon(self.pauseIcon if playing else self.playIcon)
        else:
            self.playButton.setIcon(icon)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space: 
            self.playButton.click()
        else:
            super(MainWindow, self).keyPressEvent(event)  

    @pyqtSlot(QImage)
    def __updateVideoLabel (self, image):
        if not self.videoThread.stop and self.playing:
            # print 'Updating label image'
            self.videoLabel.setPixmap(QPixmap.fromImage(image))
            self.videoLabel.update()

    @pyqtSlot()
    def __updateSlider(self):
        # print 'setting value'
        if not self.videoThread.stop and self.playing:
            self.slider.setValue(self.video.get(cv.CV_CAP_PROP_POS_FRAMES))

    @pyqtSlot()
    def __onVideoEnded(self):
        self.setPlaying(False, icon=self.replayIcon)

    @pyqtSlot()
    def __onSliderValueChanged(self):
        # print 'Slider value changed to ' + str(self.slider.value())
        if hasattr(self.window(), 'videoThread'):
            currentTime = timeString(self.slider.value() / self.videoThread.fps)
            totalTime = timeString(self.videoThread.totalSeconds)
            self.timeLabel.setText('Time: ' + currentTime + ' / ' + totalTime)
            
            currentFrame = str(self.slider.value() + 1)
            totalFrames = str(int(self.videoThread.frameCount))
            self.frameLabel.setText('Frames: ' + currentFrame + ' / ' + totalFrames)

            """
            if self.slider.isSliderDown():
                image = self.videoThread.getFrame(self.slider.value())
                if image is not None:
                    pixmap = QPixmap.fromImage(image)
                    self.videoLabel.setPixmap(pixmap)
            """
            if not self.playing or self.videoThread.stop:
                image = self.videoThread.getFrame(self.slider.value())
                if image is not None:
                    pixmap = QPixmap.fromImage(image)
                    self.videoLabel.setPixmap(pixmap)

    @pyqtSlot()
    def __onFirstFramePressed(self): 
        if self.playing:
            self.playVideoFrom(0)   
        else:
            self.playButton.setIcon(self.playIcon)
            self.slider.setValue(0)

    @pyqtSlot()
    def __onJumpBackwardPressed(self):
        newPosition = self.slider.value() - (self.slider.jumpProportion * (self.slider.maximum() + 1))

        if newPosition < 0:
            newPosition = 0

        if self.playing:
            self.playVideoFrom(newPosition)
        else:
            self.playButton.setIcon(self.playIcon) # In the case that the play icon is showing
            self.slider.setValue(newPosition)

    @pyqtSlot()
    def __onPlayPressed(self):
        if hasattr(self, 'videoThread'):
            if self.playing:
                self.stopVideo()
                self.playButton.setIcon(self.playIcon)
            else:  
                if iconsEqual(self.playButton.icon(), self.replayIcon): #Video ended
                    self.playVideoFrom(0)
                else: #Video Paused
                    self.playVideoFrom(self.slider.value())
                    self.playButton.setIcon(self.pauseIcon)

    @pyqtSlot()
    def __onJumpForwardPressed(self):
        newPosition = self.slider.value() + (self.slider.jumpProportion * (self.slider.maximum() + 1))

        if newPosition >= self.slider.maximum():
            self.lastFrameButton.click()
        else:
            if self.playing:
                self.playVideoFrom(newPosition)
            else:
                self.slider.setValue(newPosition)

    @pyqtSlot()    
    def __onLastFramePressed(self):
        if hasattr(self, 'videoThread'):
            self.stopVideo(self.replayIcon)
        self.slider.setValue(self.slider.maximum())

class VideoControlButton(QPushButton):

    def __init__(self, radius, icon):
        super(VideoControlButton, self).__init__(icon, '')

        buttonSize = QSize(radius, radius)
        self.setMask(icon.pixmap(buttonSize).mask())
        self.setFlat(True)
        self.setStyleSheet('border: none;')
        self.setIconSize(buttonSize)
        self.setMinimumSize(self.iconSize())
        self.setMaximumSize(self.iconSize())

class VideoSlider(QSlider):
    jumpProportion = .05
    
    def __init__(self, direction):
        super(VideoSlider, self).__init__(direction)
        self.setMouseTracking(True)
        self.playingBeforeMousePress = False
        self.setStyleSheet(
        """
        QSlider {
        padding-top: 5;
        padding-bottom: 5;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #CCCCCC;
            height: 2px;
            margin: 2px 0;
        }
        
        QSlider::handle:horizontal {
            image: url(images/slider7.png);
            width: 17px;
            padding-left: -1;
            padding-right: -1;
            margin: -10px 0;
        }
        """
        );

    def pixelToSliderValue(self, x):
        return int(round((float(x) / self.width()) * self.maximum()))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            event.accept()
            self.setSliderDown(True)

            if hasattr(self.window(), 'videoThread'):
                self.playingBeforeMousePress = self.window().playing
                if self.playingBeforeMousePress:
                    self.window().stopVideo(icon=self.window().pauseIcon)
                else:
                    self.window().playButton.setIcon(self.window().playIcon)

            self.setValue(self.pixelToSliderValue(event.pos().x()))

    def mouseMoveEvent(self, event):
        event.accept()
        if self.isSliderDown():
            self.setValue(self.pixelToSliderValue(event.pos().x()))

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            event.accept()
            self.setSliderDown(False)
            self.setValue(self.pixelToSliderValue(event.pos().x()))

            if hasattr(self.window(), 'videoThread'):
                if self.window().slider.value() == self.window().slider.maximum():
                    self.window().playButton.setIcon(self.window().replayIcon)
                elif self.playingBeforeMousePress:
                    self.window().playVideoFrom(self.value())

class VideoLabel(QLabel):
    
    def __init__(self):
        super(VideoLabel, self).__init__()
        self.mousePressed = False
    
    def mousePressEvent(self, event):
        self.mousePressed = True
    
    def mouseReleaseEvent(self, event):
        if self.mousePressed:
            self.window().playButton.click()
        self.mousePressed = False    

class LabelClickFilter(QObject):
    videoLabelClicked = pyqtSignal()
    
    def __init__(self, parent):
        super(LabelClickFilter, self).__init__(parent)
        self.buttonPressed = False
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            self.buttonPressed = True
        elif event.type() == QEvent.MouseButtonRelease:
            if self.buttonPressed:
                self.videoLabelClicked.emit()
            self.buttonPressed = False
        
        return QObject.eventFilter(self, obj, event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = MainWindow()
    player.show()
    sys.exit(app.exec_())

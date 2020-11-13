import cv2
import numpy as np


class WindowInfo:
    image = None
    width = 0
    height = 0

    def __init__(self, x, y, virtual=None):
        self.x = x
        self.y = y
        self.virtual = virtual


width = 1800
height = 1000
image_data = None
current_win = 0
backgrounds = None
wins = {
    "Voice Status": WindowInfo(0, 0, 0),
    "Thumb Status": WindowInfo(0, 380, 0),
    "output_video": WindowInfo(380, 0)
}


def set_active_win(active):
    global current_win
    if active != 0 and active != 1:
        print("Error: illegal win specification:", active)
        return False
    current_win = active
    if image_data:
        cv2.imshow('main-window', image_data[current_win])
    return True


def imshow(name, data):
    global image_data
    if name not in wins:
        # Open this window as normal
        cv2.imshow(name, data)
        return

    if image_data is None:
        image_data = [np.zeros((height, width, 3), np.uint8), np.zeros((height, width, 3), np.uint8)]
        if backgrounds:
            for i in range(0, min(len(backgrounds), 2)):
                i0 = cv2.imread(backgrounds[i])
                h0, w0 = i0.shape[:2]
                image_data[i][0:h0, 0:w0] = i0

    h1, w1 = data.shape[:2]
    info = wins[name]
    info.width = w1
    info.height = h1
    if len(data.shape) == 2:
        data = cv2.cvtColor(data, cv2.COLOR_GRAY2BGR)
    active = current_win if info.virtual is None else info.virtual
    image_data[active][info.y:info.y + h1, info.x:info.x + w1] = data
    if info.virtual == current_win:
        cv2.imshow('main-window', image_data[current_win])

"""Application package.

This module runs before any ``app.*`` submodule (and therefore before OpenCV
is first imported), so it is the right place to set OpenCV environment
variables that must be in effect before the video I/O backends initialize.
"""
import os

# OpenCV's Media Foundation (MSMF) backend silently fails to open some cameras
# on Windows when hardware transforms are enabled - VideoCapture(index, CAP_MSMF)
# reports isOpened()==False and we fall back to DirectShow, which for the Canon
# EOS Webcam Utility only ever delivers black frames. Disabling MSMF hardware
# transforms lets MSMF open the device (the same path Teams/Windows Camera use),
# so the driver's placeholder/live feed is shown instead of black. Must be set
# before cv2 is imported; setdefault so an operator can still override it.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

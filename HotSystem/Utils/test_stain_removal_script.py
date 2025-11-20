import matplotlib
matplotlib.use("TkAgg")  # You can also try "Qt5Agg" or "QtAgg" if installed
import matplotlib.pyplot as plt

from Utils.python_displayer import test_calib_stains_viewer

# Disable interactive mode and block until closed
plt.ioff()
test_calib_stains_viewer()
plt.show(block=True)
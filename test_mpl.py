import sys
from PyQt6.QtWidgets import QApplication
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt

app = QApplication(sys.argv)
plt.figure("Test")
plt.plot([1, 2, 3], [4, 5, 6])
plt.show(block=False)

print("Figure shown")
# Don't block forever, just enough to verify
sys.exit(0)

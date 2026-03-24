import sys
import qtawesome as qta
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
icon = qta.icon('fa5s.save', color='red')
pixmap = icon.pixmap(64, 64)
pixmap.save("test_qta.png")

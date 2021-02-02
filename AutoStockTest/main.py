import sys
from PyQt5.QtWidgets import QApplication
from kiwoom.kiwoom import *

class Main():
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.kiwoom = Kiwoom()
        self.app.exec_()  # event loop 실행




if __name__ == "__main__":
    Main()
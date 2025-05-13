import sys
from PyQt6.QtWidgets import QApplication
from ui import DisenchanterApp # To be created later

def main():
    app = QApplication(sys.argv)
    window = DisenchanterApp() # To be created later
    window.show() # To be created later
    sys.exit(app.exec()) # To be uncommented later

if __name__ == "__main__":
    main() 
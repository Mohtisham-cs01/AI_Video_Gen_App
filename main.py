import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ui.main_window import App

if __name__ == "__main__":
    app = App()
    app.mainloop()

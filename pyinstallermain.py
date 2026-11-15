import sys
import os
from runtime import TIC80Runtime


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = resource_path("game.py")

    runtime = TIC80Runtime(filename)
    runtime.run()


if __name__ == "__main__":
    main()

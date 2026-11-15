
import sys
from runtime import TIC80Runtime


def main():

    filename = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "games/game222.py"
    )

    runtime = TIC80Runtime(filename)
    runtime.run()


if __name__ == "__main__":
    main()

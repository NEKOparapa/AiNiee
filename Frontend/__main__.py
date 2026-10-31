"""Run the desktop with python -m Frontend."""
import multiprocessing
import sys


if __name__ == "__main__":
    multiprocessing.freeze_support()
    from Frontend.app.bootstrap import main
    sys.exit(main())

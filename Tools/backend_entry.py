"""Entry point for the independently frozen backend executable."""
import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()
    from Backend.__main__ import main
    main()

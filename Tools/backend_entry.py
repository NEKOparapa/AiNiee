"""Entry point for the independently frozen backend executable."""
import multiprocessing
import sys


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--check-media-tools"]:
        import json
        from Backend.core.media_tools_check import check_bundled_media_tools
        try:
            result = check_bundled_media_tools()
        except Exception as error:
            if sys.stderr is not None:
                print(f"Bundled media tool check failed: {error}", file=sys.stderr)
            sys.exit(1)
        if sys.stdout is not None:
            print(json.dumps(result))
    else:
        from Backend.__main__ import main
        main()

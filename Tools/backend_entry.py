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
    elif sys.argv[1:] == ["--check-pdf-runtime"]:
        from importlib.metadata import version

        if sys.stdout is not None:
            print(f"Checking PDF runtime with BabelDOC {version('babeldoc')}", flush=True)
        # Import the same adapter used by real PDF requests and the native
        # modules that BabelDOC otherwise defers until a document is opened.
        from Backend.infrastructure.files.accessors.babeldoc_pdf_accessor import BabeldocPdfAccessor
        from babeldoc._rust_il import MDocument
        from babeldoc.docvision.doclayout import OnnxModel
    else:
        from Backend.__main__ import main
        main()

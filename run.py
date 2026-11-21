import os
import sys
from pathlib import Path

# Keep Tcl paths relative on Windows hosts that remap profile directories.
# The PyInstaller tkinter runtime hook runs before this entry point.
if getattr(sys, "frozen", False):
    os.chdir(Path(sys.executable).parent)
    os.environ["TCL_LIBRARY"] = "_internal/_tcl_data"
    os.environ["TK_LIBRARY"] = "_internal/_tk_data"

from health_manager.app import main

if __name__ == "__main__":
    main()

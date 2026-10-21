"""支持 `python -m mcd_mate` 直接启动 CLI。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
Entry point for the master logging server.

Run this as a standalone process to handle centralised logging for all
application components.  Both MasterConsoleLogger and MasterFileLogger are
started here; their threads are joined so the process stays alive until an
external stop command is received.

Import-time side-effect
───────────────────────
When this module is imported (rather than executed directly) the loggers are
also started.  This supports frameworks that import entry-point modules rather
than running them with ``__main__``.
"""
import sys

from logutils.CentralLoggers import startLoggers, MasterConsoleLogger, MasterFileLogger

from Configuration import *

CosThetaConfigurator.getInstance()


def main() -> None:
    """Start both master loggers and block until they finish."""
    startLoggers()          # handles start(), join(), and sys.exit()


# if __name__ == "__main__":
#     main()
# else:
#     # Imported as a module — start loggers but do not block or exit
#     _mcl = MasterConsoleLogger()
#     _mfl = MasterFileLogger()
#     _mcl.start()
#     _mfl.start()

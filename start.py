# LEDD Project
# Copyright (C) 2015 LEDD Team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import ledd.daemon
import sys
import os

from pkgutil import iter_modules

if "smbus" not in (name for loader, name, ispkg in iter_modules()):
    print("smbus not found, installing replacement")


    class SMBus:
        def __init__(self, i2c_address):
            self.i2c_address = i2c_address
            self.channels = {}

        def write_word_data(self, addr, cmd, val):
            if (cmd - 6) % 4 == 0:
                self.channels[(cmd - 6) // 4] = val

        def read_word_data(self, addr, cmd):
            if (cmd - 8) // 4 not in self.channels:
                self.channels[(cmd - 8) // 4] = 0
            return self.channels[(cmd - 8) // 4]


    class SMBusModule:
        SMBus = SMBus


    sys.modules['smbus'] = SMBusModule
    sys.modules['smbus'].SMBus = SMBus

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
                        datefmt="%H:%M:%S")
    log = logging.getLogger(__name__)

    wdir = os.path.dirname(os.path.realpath(__file__))
    try:
        pid = os.fork()
        if pid == 0:
            os.setsid()
            pid2 = os.fork()
            if pid2 == 0:
                os.umask(0)
                os.chdir(wdir)
                daemon = ledd.daemon.Daemon()
            else:
                sys.exit()
        else:
            sys.exit()
    except OSError as e:
        log.fatal("Start failed: %s", e)

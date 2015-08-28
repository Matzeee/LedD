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

    import sys

    sys.modules['smbus'] = SMBusModule
    sys.modules['smbus'].SMBus = SMBus

import ledd.daemon

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
                        datefmt="%H:%M:%S")
    log = logging.getLogger(__name__)
    daemon = ledd.daemon.Daemon()

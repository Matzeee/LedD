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

import configparser
import socket
import json
import uuid


class TestDaemon:
    s = None
    """ :type : socket.socket """

    @classmethod
    def setup_class(cls):
        daemon_section = 'daemon'
        config = configparser.ConfigParser()
        try:
            with open('ledd.config', 'w+') as f:
                config.read_file(f)
        except FileNotFoundError:
            pass

        cls.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.s.settimeout(20)
        cls.s.connect((config.get(daemon_section, 'host', fallback='0.0.0.0'),
                       config.get(daemon_section, 'port', fallback=1425)))

    @classmethod
    def teardown_class(cls):
        cls.s.close()

    def test_discover(self):
        ref = uuid.uuid4().urn[9:]
        sjson = {
            "action": "discover",
            "ref": ref
        }

        self.s.send(json.dumps(sjson).encode())

        rstr = self.s.recv(1024).decode()

        assert rstr is not None

        rjson = json.loads(rstr)
        assert rjson['ref'] == ref
        assert rjson['version'] is not None

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

import asyncore
import socket
import configparser


class Daemon:

    daemonSection = 'daemon'

    def __init__(self):
        config = configparser.ConfigParser()
        try:
            with open('ledd.config', 'w+') as f:
                config.read_file(f)
        except FileExistsError:
            print("no config file found!")

        server = self.SocketServer(config.get(self.daemonSection, 'host', fallback='0.0.0.0'),
                                   config.get(self.daemonSection, 'port', fallback=1425))
        asyncore.loop()

    class ConnectionHandler(asyncore.dispatcher_with_send):

        def handle_read(self):
            data = self.recv(8192)
            if data:
                print(data)

    class SocketServer(asyncore.dispatcher):

        def __init__(self, host, port):
            asyncore.dispatcher.__init__(self)
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            self.set_reuse_addr()
            self.bind((host, port))
            self.listen(5)

        def handle_accept(self):
            pair = self.accept()
            if pair is not None:
                sock, addr = pair
                print('Incoming connection from %s' % repr(addr))
                handler = Daemon.ConnectionHandler(sock)

if __name__ == "__main__":
    daemon = Daemon()

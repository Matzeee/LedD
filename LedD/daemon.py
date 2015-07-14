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
import json
import sqlite3
import os
import sys

from . import controller


class Daemon:
    daemonSection = 'daemon'
    databaseSection = 'db'
    instance = None

    def __init__(self):
        Daemon.instance = self
        try:
            self.config = configparser.ConfigParser()
            try:
                with open('ledd.config', 'w+') as f:
                    self.config.read_file(f)
            except FileNotFoundError:
                print("no config file found!")

            self.sqldb = sqlite3.connect(self.config.get(self.databaseSection, 'name', fallback='ledd.sqlite'))
            self.sqldb.row_factory = sqlite3.Row

            if not self.check_db():
                self.init_db()

            self.sqldb.commit()

            self.controllers = controller.Controller.from_db(self.sqldb)
            print(self.controllers)

            server = self.SocketServer(self.config.get(self.daemonSection, 'host', fallback='0.0.0.0'),
                                       self.config.get(self.daemonSection, 'port', fallback=1425))
            asyncore.loop()
        except (KeyboardInterrupt, SystemExit):
            print("\nShutting down...")
            self.sqldb.close()
            sys.exit(0)

    def check_db(self):
        c = self.sqldb.cursor()
        try:
            c.execute("SELECT value FROM meta WHERE option = 'db_version'")
            db_version = c.fetchone()
            c.close()

            if db_version is not None:
                print("DB connection established; version={}".format(db_version[0]))
                return True
            else:
                return False
        except sqlite3.OperationalError:
            c.close()
            return False

    def init_db(self):
        self.sqldb.close()
        if os.path.exists("ledd.sqlite"):
            os.remove("ledd.sqlite")
        self.sqldb = sqlite3.connect(self.config.get(self.databaseSection, 'name', fallback='ledd.sqlite'))
        self.sqldb.row_factory = sqlite3.Row
        with open("LedD/sql/ledd.sql", "r") as sqlfile:
            c = self.sqldb.cursor()
            c.executescript(sqlfile.read())
            c.close()
        self.check_db()

    class ConnectionHandler(asyncore.dispatcher_with_send):
        def handle_read(self):
            data = self.recv(5120)
            self.debug = True
            if data:
                print(data)
                try:
                    json_decoded = json.loads(data.decode())
                    print(json.dumps(json_decoded, sort_keys=True, indent=4, separators=(',', ': ')))

                    if "action" in json_decoded:
                        if json_decoded['action'] == "set_color":
                            # TODO: add adapter setting stripe with color here
                            print("recieved action: {}".format(json_decoded['action']))
                        elif json_decoded['action'] == "add_controller":
                            print("recieved action: {}".format(json_decoded['action']))
                            ncontroller = None
                            try:
                                ncontroller = controller.Controller(Daemon.instance.sqldb, json_decoded['channels'],
                                                                    json_decoded['i2c_dev'], json_decoded['address'])
                            except OSError as e:
                                print("Error opening i2c device!")
                            self.send("{}\n".format(ncontroller.id).encode())
                            Daemon.instance.controllers.append(ncontroller)
                        elif json_decoded['action'] == "get_color":
                            # TODO: add stripe color get logic
                            print("recieved action: {}".format(json_decoded['action']))
                        elif json_decoded['action'] == "add_stripes":
                            if "stripes" in json_decoded:
                                for stripe in json_decoded['stripes']:
                                    # TODO: add stripe here
                                    print(len(json_decoded['stripes']))
                    else:
                        print("no action found, ignoring")
                except TypeError as e:
                    print("No valid JSON found: {}".format(e))
                except ValueError:
                    print("No valid JSON detected!")

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

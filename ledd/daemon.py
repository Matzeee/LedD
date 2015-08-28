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
import configparser
import json
import sqlite3
import os
import sys
import traceback
import time
import asyncio

from ledd import controller, VERSION
from ledd.decorators import ledd_protocol

log = logging.getLogger(__name__)


class Daemon:
    daemonSection = 'daemon'
    databaseSection = 'db'
    instance = None
    """:type : Daemon """
    loop = None
    """ :type : asyncio.BaseEventLoop """
    protocol = {}

    def __init__(self):
        Daemon.instance = self

        try:
            self.config = configparser.ConfigParser()
            try:
                with open('ledd.config', 'w+') as f:
                    self.config.read_file(f)
            except FileNotFoundError:
                log.info("No config file found!")

            self.sqldb = sqlite3.connect(self.config.get(self.databaseSection, 'name', fallback='ledd.sqlite'))
            self.sqldb.row_factory = sqlite3.Row

            if not self.check_db():
                self.init_db()

            self.sqldb.commit()

            self.controllers = controller.Controller.from_db(self.sqldb)
            log.debug(self.controllers)
            logging.getLogger("asyncio").setLevel(logging.DEBUG)

            self.loop = asyncio.get_event_loop()
            coro = self.loop.create_server(LedDProtocol,
                                           self.config.get(self.daemonSection, 'host', fallback='0.0.0.0'),
                                           self.config.get(self.daemonSection, 'port', fallback=1425))
            server = self.loop.run_until_complete(coro)
            self.loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            log.info("Exiting")
            self.sqldb.close()
            self.loop.run_until_complete(server.wait_closed())
            self.loop.close()
            sys.exit(0)

    def check_db(self):
        """
        Checks database version
        :return: database validity
        :rtype: bool
        """
        c = self.sqldb.cursor()
        try:
            c.execute("SELECT value FROM meta WHERE option = 'db_version'")
            db_version = c.fetchone()
            c.close()

            if db_version is not None:
                log.info("DB connection established; db-version=%s", db_version[0])
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
        with open("ledd/sql/ledd.sql", "r") as sqlfile:
            c = self.sqldb.cursor()
            c.executescript(sqlfile.read())
            c.close()
        self.check_db()

    @ledd_protocol(protocol)
    def set_color(self, req_json):
        """
        Part of the Color API. Used to set color of a stripe.
        Required JSON parameters: stripe ID: sid; HSV values: h,s,v
        :param req_json: dict of request json
        """
        # TODO: add adapter setting stripe with color here
        log.debug("recieved action: %s", req_json['action'])

    @ledd_protocol(protocol)
    def add_controller(self, req_json):
        """
        Part of the Color API. Used to add a controller.
        Required JSON parameters: channels; i2c_dev: number of i2c device (e.g. /dev/i2c-1 would be i2c_dev = 1);
                                  address: hexdecimal address of controller on i2c bus, e.g. 0x40
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])
        try:
            ncontroller = controller.Controller(Daemon.instance.sqldb, req_json['channels'],
                                                req_json['i2c_dev'], req_json['address'])
        except OSError as e:
            log.error("Error opening i2c device: %s", req_json['i2c_dev'])
            rjson = {
                'success': False,
                'message': "Error while opening i2c device",
                'message_detail': os.strerror(e.errno),
                'ref': req_json['ref']
            }
            return json.dumps(rjson)

        self.controllers.append(ncontroller)

        rjson = {
            'success': True,
            'cid': ncontroller.id,
            'ref': req_json['ref']
        }

        return json.dumps(rjson)

    @ledd_protocol(protocol)
    def get_color(self, req_json):
        """
        Part of the Color API. Used to get the currect color of an stripe.
        Required JSON parameters: stripeid: sid
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])
        # TODO: Add get color logic

    @ledd_protocol(protocol)
    def add_stripes(self, req_json):
        """
        Part of the Color API. Used to add stripes.
        Required JSON parameters:
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])
        if "stripes" in req_json:
            for stripe in req_json['stripes']:

                log.debug(len(req_json['stripes']))

    @ledd_protocol(protocol)
    def get_controllers(self, req_json):
        """
        Part of the Color API. Used to get all registered controllers known to the daemon.
        Required JSON parameters: none
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        rjson = {
            'success': True,
            'ccount': len(Daemon.instance.controllers),
            'controller': Daemon.instance.controllers,
            'ref': req_json['ref']
        }

        return json.dumps(rjson, cls=controller.ControllerEncoder)

    @ledd_protocol(protocol)
    def connection_check(self, req_json):
        """
        Part of the Color API. Used to query all channels on a specified controller.
        Required JSON parameters: controller id: cid
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        result = next(filter(lambda x: x.id == req_json['cid'], self.controllers), None)
        """ :type : Controller """

        if result is not None:
            for i in range(result.channels):
                log.debug("set channel %d=%s", i, "1")
                result.set_channel(i, 1)
                time.sleep(10)
                result.set_channel(i, 0)

        rjson = {
            'success': True,
            'ref': req_json['ref']
        }

        return json.dumps(rjson)

    @ledd_protocol(protocol)
    def discover(self, req_json):
        """
        Part of the Color API. Used by mobile applications to find the controller.
        Required JSON parameters: none
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        rjson = {
            'success': True,
            'ref': req_json['ref'],
            'version': VERSION
        }

        return json.dumps(rjson)


class LedDProtocol(asyncio.Protocol):
    transport = None

    def connection_made(self, transport):
        log.info("New connection from %s", transport.get_extra_info("peername"))
        self.transport = transport

    def data_received(self, data):
        log.info("Received: %s\nfrom: ", data.decode(), self.transport.get_extra_info("peername"))
        self.select_task(data)

    def select_task(self, data):
        if data:
            try:
                json_decoded = json.loads(data.decode())

                if "action" in json_decoded and "ref" in json_decoded:
                    return_data = Daemon.instance.protocol.get(json_decoded['action'], self.no_action_found)(
                        json_decoded)

                    if return_data is not None:
                        self.transport.write("{}\n".format(return_data).encode())
                else:
                    log.debug("no action or ref value found in JSON, ignoring")
            except TypeError:
                log.debug("No valid JSON found: %s", traceback.format_exc())
            except ValueError:
                log.debug("No valid JSON detected: %s", traceback.format_exc())

    @staticmethod
    def no_action_found(req_json):
        rjson = {
            'success': False,
            'message': "No action found",
            'ref': req_json['ref']
        }
        return json.dumps(rjson)

    def connection_lost(self, exc):
        # The socket has been closed, stop the event loop
        # Daemon.loop.stop()
        log.info("Lost connection to %s", self.transport.get_extra_info("peername"))

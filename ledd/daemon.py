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

import spectra

from zeroconf import Zeroconf, ServiceInfo

from ledd import controller, VERSION
from ledd.decorators import ledd_protocol
from ledd.effectstack import EffectStack
from ledd.stripe import Stripe

log = logging.getLogger(__name__)


class Daemon:
    daemonSection = 'daemon'
    databaseSection = 'db'
    instance = None
    """:type : Daemon """
    loop = None
    """ :type : asyncio.BaseEventLoop """
    protocol = {}
    effects = []

    def __init__(self):
        Daemon.instance = self

        try:
            # read config
            self.config = configparser.ConfigParser()
            try:
                with open('ledd.config', 'w+') as f:
                    self.config.read_file(f)
            except FileNotFoundError:
                log.info("No config file found!")

            # create zeroconf service info
            self.zinfo = ServiceInfo("_ledd._tcp.local.", "LedD Daemon._ledd._tcp.local.",
                                     port=self.config.get(self.daemonSection, 'port', fallback=1425))

            # SQL init
            self.sqldb = sqlite3.connect(self.config.get(self.databaseSection, 'name', fallback='ledd.sqlite'))
            self.sqldb.row_factory = sqlite3.Row

            if not self.check_db():
                self.init_db()

            self.sqldb.commit()

            # init controllers from db
            self.controllers = controller.Controller.from_db(self.sqldb)
            log.debug(self.controllers)
            logging.getLogger("asyncio").setLevel(logging.DEBUG)

            # announce server to network
            self.register_zeroconf()

            # main loop
            self.loop = asyncio.get_event_loop()
            coro = self.loop.create_server(LedDProtocol,
                                           self.config.get(self.daemonSection, 'host', fallback='0.0.0.0'),
                                           self.config.get(self.daemonSection, 'port', fallback=1425))
            self.server = self.loop.run_until_complete(coro)
            self.loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            log.info("Exiting")
            self.deregister_zeroconf()
            self.sqldb.close()
            self.server.close()
            self.loop.run_until_complete(self.server.wait_closed())
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

    def register_zeroconf(self):
        try:
            zeroconf = Zeroconf()
            zeroconf.register_service(self.zinfo)
            log.info("Registered ledd daemon with zeroconf")
        except OSError as e:
            log.warning("Failed to register service with ZeroConf: %s", e)
            pass

    def deregister_zeroconf(self):
        try:
            zeroconf = Zeroconf()
            zeroconf.unregister_service(self.zinfo)
            log.info("Unregistered ledd daemon with zeroconf")
        except OSError as e:
            log.warning("Failed to deregister service with ZeroConf: %s", e)
            pass

    @ledd_protocol(protocol)
    def start_effect(self, req_json):
        """

        :param req_json: dict of request json
        """
        effect = EffectStack()
        self.effects.append(effect)
        effect.stripes.append(self.controllers[1].stripes[0])
        effect.start()

        # asyncio.ensure_future(asyncio.get_event_loop().run_in_executor(self.executor, effect.execute))

        log.debug("recieved action: %s", req_json['action'])

    @ledd_protocol(protocol)
    def start_effect(self, req_json):
        """

        :param req_json: dict of request json
        """
        effect = BaseEffect(Stripe(),self.loop)
        self.effects.append(effect)
        asyncio.ensure_future(asyncio.get_event_loop().run_in_executor(self.executor, effect.execute))

        log.debug("recieved action: %s", req_json['action'])

    @ledd_protocol(protocol)
    def set_color(self, req_json):
        """
        Part of the Color API. Used to set color of a stripe.
        Required JSON parameters: stripe ID: sid; HSV values hsv: h,s,v, controller id: cid
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        if "stripes" in req_json:
            for stripe in req_json['stripes']:
                found_s = self.find_stripe(stripe)

                if found_s is None:
                    log.warning("Stripe not found: id=%s", stripe['sid'])
                    continue

                found_s.set_color(spectra.hsv(stripe['hsv']['h'], stripe['hsv']['s'], stripe['hsv']['v']))

    def find_stripe(self, jstripe):
        """
        Finds a given stripeid in the currently known controllers
        :param jstripe: json containing sid
        :return: stripe if found or none
        :rtype: ledd.Stripe | None
        """
        for c in self.controllers:
            for s in c.stripes:
                if s.id == jstripe['sid']:
                    return s

        return None

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
        Required JSON parameters: stripes
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        res_stripes = []

        if "stripes" in req_json:
            for stripe in req_json['stripes']:
                found_s = self.find_stripe(stripe)

                if found_s is None:
                    log.warning("Stripe not found: id=%s", stripe['sid'])
                    continue

                res_stripes.append({
                    'success': True,
                    'sid': found_s.id,
                    'color': found_s.get_color.values
                })

            rjson = {
                'success': True,
                'stripes': res_stripes,
                'ref': req_json['ref']
            }

            return json.dumps(rjson)

    @ledd_protocol(protocol)
    def add_stripes(self, req_json):
        """
        Part of the Color API. Used to add stripes.
        Required JSON parameters: name; rgb: bool; map: r: r-channel, g: g-channel, b: b-channel
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        res_stripes = []

        if "stripes" in req_json:
            for stripe in req_json['stripes']:
                c = next((x for x in self.controllers if x.id == stripe['cid']), None)

                if c is None:
                    res_stripes.append({
                        'success': False,
                        'message': "Controller not found",
                        'ref': stripe['ref']
                    })
                    continue

                s = Stripe(c, stripe['name'], stripe['rgb'],
                           (stripe['map']['r'], stripe['map']['g'], stripe['map']['b']))

                res_stripes.append({
                    'success': True,
                    'sid': s.id,
                    'ref': stripe['ref']
                })

            rjson = {
                'success': True,
                'stripes': res_stripes,
                'ref': req_json['ref']
            }

            return json.dumps(rjson)

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

    def no_action_found(self, req_json):
        rjson = {
            'success': False,
            'message': "No action found",
            'ref': req_json['ref']
        }
        return json.dumps(rjson)


class LedDProtocol(asyncio.Protocol):
    transport = None

    def connection_made(self, transport):
        log.info("New connection from %s", transport.get_extra_info("peername"))
        self.transport = transport

    def data_received(self, data):
        log.info("Received: %s from: %s", data.decode(), self.transport.get_extra_info("peername"))
        self.select_task(data)

    def select_task(self, data):
        if data:
            try:
                json_decoded = json.loads(data.decode())

                if "action" in json_decoded and "ref" in json_decoded:
                    return_data = Daemon.instance.protocol.get(json_decoded['action'], Daemon.no_action_found)(
                        Daemon.instance, json_decoded)

                    if return_data is not None:
                        self.transport.write("{}\n".format(return_data).encode())
                else:
                    log.debug("no action or ref value found in JSON, ignoring")
            except TypeError:
                log.debug("No valid JSON found: %s", traceback.format_exc())
            except ValueError:
                log.debug("No valid JSON detected: %s", traceback.format_exc())

    def connection_lost(self, exc):
        # The socket has been closed, stop the event loop
        # Daemon.loop.stop()
        log.info("Lost connection to %s", self.transport.get_extra_info("peername"))

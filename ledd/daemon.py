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
import asyncio
import signal

from jsonrpc import JSONRPCResponseManager, dispatcher

from jsonrpc.exceptions import JSONRPCError
import spectra

from ledd import controller, VERSION
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
                pass

            # SQL init
            self.sqldb = sqlite3.connect(self.config.get(self.databaseSection, 'name', fallback='ledd.sqlite'))
            self.sqldb.row_factory = sqlite3.Row

            if not self.check_db():
                self.init_db()

            self.sqldb.commit()

            # init controllers from db
            self.controllers = controller.Controller.from_db(self.sqldb)
            log.debug(self.controllers)
            logging.getLogger("asyncio").setLevel(log.getEffectiveLevel())

            # sigterm handler
            def sigterm_handler():
                raise SystemExit

            signal.signal(signal.SIGTERM, sigterm_handler)

            # init plugins
            # TODO: check all plugins for existing hooks

            # main loop
            self.loop = asyncio.get_event_loop()
            coro = self.loop.create_server(LedDProtocol,
                                           self.config.get(self.daemonSection, 'host', fallback='0.0.0.0'),
                                           self.config.get(self.daemonSection, 'port', fallback=1425))
            self.server = self.loop.run_until_complete(coro)
            self.loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            log.info("Exiting")
            try:
                os.remove("ledd.pid")
            except FileNotFoundError:
                pass
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

                if int(db_version[0]) < 2:
                    with open("ledd/sql/upgrade_1_2.sql", "r") as ufile:
                        u = self.sqldb.cursor()
                        u.executescript(ufile.read())
                        u.close()
                        log.info("Database upgraded to version %s", 2)

                return True
            else:
                return False
        except sqlite3.OperationalError as e:
            log.debug("SQLite error: %s", e)
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

    @dispatcher.add_method
    def start_effect(self, **kwargs):
        """
        Part of the Color API. Used to start a specific effect.
        Required JSON parameters: stripe IDs: sids; effect id: eid, effect options: eopt
        :param req_json: dict of request json
        """
        stripes = []

        if "sids" in kwargs:
            for sid in kwargs['sids']:
                found_s = self.find_stripe(sid)

                if found_s is not None:
                    stripes.append(found_s)

        if len(stripes) > 0:
            # TODO: add anything required to start effect with req_json['eid']
            # on stripes[] with options in req_json['eopt']
            effect = EffectStack()
            self.effects.append(effect)
            effect.stripes.append(self.controllers[0].stripes[0])
            effect.start()

            # asyncio.ensure_future(asyncio.get_event_loop().run_in_executor(self.executor, effect.execute))

            rjson = {
                'eident': None,  # unique effect identifier that identifies excatly this effect started on this set of
                # stripes, used to stop them later and to give informations about running effects
            }

            return rjson
        else:
            return JSONRPCError(-1003, "Stripeid not found")

    @dispatcher.add_method
    def stop_effect(self, **kwargs):
        """
        Part of the Color API. Used to stop a specific effect.
        Required JSON parameters: effect identifier: eident
        :param req_json: dict of request json
        """

        # TODO: add stop effect by eident logic

    @dispatcher.add_method
    def get_effects(self, **kwargs):
        """
        Part of the Color API. Used to show all available and running effects.
        Required JSON parameters: -
        :param req_json: dict of request json
        """

        # TODO: list all effects here and on which stripes they run atm
        # TODO: all effects get runtime only ids, "eid"'s. They are shown here for the client to start effects.
        # TODO: All options that an effect may have need to be transmitted here too with "eopt".

    @dispatcher.add_method
    def set_color(self, **kwargs):
        """
        Part of the Color API. Used to set color of a stripe.
        Required JSON parameters: stripe ID: sid; HSV values hsv: h,s,v, controller id: cid
        :param req_json: dict of request json
        """

        found_s = self.find_stripe(kwargs['sid'])

        if found_s is None:
            log.warning("Stripe not found: id=%s", kwargs['sid'])
        else:
            found_s.set_color(spectra.hsv(kwargs['hsv']['h'], kwargs['hsv']['s'], kwargs['hsv']['v']))

    @dispatcher.add_method
    def add_controller(self, **kwargs):
        """
        Part of the Color API. Used to add a controller.
        Required JSON parameters: channels; i2c_dev: number of i2c device (e.g. /dev/i2c-1 would be i2c_dev = 1);
                                  address: hexdecimal address of controller on i2c bus, e.g. 0x40
        :param req_json: dict of request json
        """
        try:
            ncontroller = controller.Controller(Daemon.instance.sqldb, kwargs['channels'],
                                                kwargs['i2c_dev'], kwargs['address'])
        except OSError as e:
            log.error("Error opening i2c device: %s (%s)", kwargs['i2c_dev'], e)
            return JSONRPCError(-1004, "Error while opening i2c device", e)

        self.controllers.append(ncontroller)

        rjson = {
            'cid': ncontroller.id,
        }

        return rjson

    @dispatcher.add_method
    def get_color(self, **kwargs):
        """
        Part of the Color API. Used to get the current color of an stripe.
        Required JSON parameters: stripes
        :param req_json: dict of request json
        """

        found_s = self.find_stripe(kwargs['sid'])

        if found_s is None:
            log.warning("StripeId not found: id=%s", kwargs['sid'])
            return JSONRPCError(-1003, "Stripeid not found")

        rjson = {
            'color': found_s.color.values,
        }

        return rjson

    @dispatcher.add_method
    def add_stripe(self, **kwargs):
        """
        Part of the Color API. Used to add stripes.
        Required JSON parameters: name; rgb: bool; map: r: r-channel, g: g-channel, b: b-channel, cid
        :param req_json: dict of request json
        """

        if "stripe" in kwargs:
            stripe = kwargs['stripe']
            c = next((x for x in self.controllers if x.id == stripe['cid']), None)
            """ :type c: ledd.controller.Controller """

            if c is None:
                return JSONRPCError(-1002, "Controller not found")

            s = Stripe(c, stripe['name'], stripe['rgb'],
                       (stripe['map']['r'], stripe['map']['g'], stripe['map']['b']))

            c.stripes.append(s)
            log.debug("Added stripe %s to controller %s; new len %s", c.id, s.id, len(c.stripes))

            rjson = {
                'sid': s.id,
            }

            return rjson

    @dispatcher.add_method
    def get_stripes(self, **kwargs):
        """
        Part of the Color API. Used to get all registered stripes known to the daemon.
        Required JSON parameters: none
        :param req_json: dict of request json
        """

        rjson = {
            'ccount': len(Daemon.instance.controllers),
            'controller': json.dumps(Daemon.instance.controllers, cls=controller.ControllerEncoder),
        }

        return rjson

    @dispatcher.add_method
    def test_channel(self, **kwargs):
        """
        Part of the Color API. Used to test a channel on a specified controller.
        Required JSON parameters: controller id: cid, channel, value
        :param req_json: dict of request json
        """

        result = next(filter(lambda x: x.id == kwargs['cid'], self.controllers), None)
        """ :type : ledd.controller.Controller """

        if result is not None:
            result.set_channel(kwargs['channel'], kwargs['value'], 2.8)

    @dispatcher.add_method
    def discover(self, **kwargs):
        """
        Part of the Color API. Used by mobile applications to find the controller.
        Required JSON parameters: none
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", kwargs['action'])

        rjson = {
            'version': VERSION
        }

        return rjson

    def find_stripe(self, sid):
        """
        Finds a given stripeid in the currently known controllers
        :param sid stripe id
        :return: stripe if found or none
        :rtype: ledd.Stripe | None
        """
        for c in self.controllers:
            for s in c.stripes:
                if s.id == sid:
                    return s

        return None


class LedDProtocol(asyncio.Protocol):
    transport = None

    def connection_made(self, transport):
        log.debug("New connection from %s", transport.get_extra_info("peername"))
        self.transport = transport

    def data_received(self, data):
        try:
            d_decoded = data.decode()
        except UnicodeDecodeError:
            log.warning("Recieved undecodable data, ignoring")
        else:
            log.debug("Received: %s from: %s", d_decoded, self.transport.get_extra_info("peername"))
            self.select_task(d_decoded)

    def select_task(self, data):
        if data:
            data_split = data.splitlines()
            log.debug(data_split)
            for line in data_split:
                if line:
                    self.transport.write(JSONRPCResponseManager.handle(line, dispatcher))

    def connection_lost(self, exc):
        # The socket has been closed, stop the event loop
        # Daemon.loop.stop()
        log.info("Lost connection to %s", self.transport.get_extra_info("peername"))

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
import asyncio
import signal

import spectra

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
            def sigterm_handler(_signo, _stack_frame):
                sys.exit(0)

            signal.signal(signal.SIGTERM, sigterm_handler)

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
    def start_effect(self, req_json):
        """
        Part of the Color API. Used to start a specific effect.
        Required JSON parameters: stripe IDs: sids; effect id: eid, effect options: eopt
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        stripes = []

        if "sids" in req_json:
            for sid in req_json['sids']:
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
                'success': True,
                'eident': None,  # unique effect identifier that identifies excatly this effect started on this set of
                # stripes, used to stop them later and to give informations about running effects
                'ref': req_json['ref']
            }

            return json.dumps(rjson)
        else:
            rjson = {
                'success': False,
                'message': "No stripe with this id found",
                'ref': req_json['ref']
            }

            return json.dumps(rjson)

    @ledd_protocol(protocol)
    def stop_effect(self, req_json):
        """
        Part of the Color API. Used to stop a specific effect.
        Required JSON parameters: effect identifier: eident
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        # TODO: add stop effect by eident logic

    @ledd_protocol(protocol)
    def get_effects(self, req_json):
        """
        Part of the Color API. Used to show all available and running effects.
        Required JSON parameters: -
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        # TODO: list all effects here and on which stripes they run atm
        # TODO: all effects get runtime only ids, "eid"'s. They are shown here for the client to start effects.
        # TODO: All options that an effect may have need to be transmitted here too with "eopt".

    @ledd_protocol(protocol)
    def set_color(self, req_json):
        """
        Part of the Color API. Used to set color of a stripe.
        Required JSON parameters: stripe ID: sid; HSV values hsv: h,s,v, controller id: cid
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        found_s = self.find_stripe(req_json['sid'])

        if found_s is None:
            log.warning("Stripe not found: id=%s", req_json['sid'])
        else:
            found_s.set_color(spectra.hsv(req_json['hsv']['h'], req_json['hsv']['s'], req_json['hsv']['v']))

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
            log.error("Error opening i2c device: %s (%s)", req_json['i2c_dev'], os.strerror(int(str(e))))
            rjson = {
                'success': False,
                'message': "Error while opening i2c device",
                'message_detail': os.strerror(int(str(e))),
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
        Part of the Color API. Used to get the current color of an stripe.
        Required JSON parameters: stripes
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        found_s = self.find_stripe(req_json['sid'])

        if found_s is None:
            log.warning("Stripe not found: id=%s", req_json['sid'])
            return {
                'success': False,
                'message': "Stripe not found",
                'ref': req_json['ref']
            }

        rjson = {
            'success': True,
            'color': found_s.color.values,
            'ref': req_json['ref']
        }

        return json.dumps(rjson)

    @ledd_protocol(protocol)
    def add_stripe(self, req_json):
        """
        Part of the Color API. Used to add stripes.
        Required JSON parameters: name; rgb: bool; map: r: r-channel, g: g-channel, b: b-channel, cid
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        if "stripe" in req_json:
            stripe = req_json['stripe']
            c = next((x for x in self.controllers if x.id == stripe['cid']), None)
            """ :type c: ledd.controller.Controller """

            if c is None:
                return {
                    'success': False,
                    'message': "Controller not found",
                    'ref': stripe['ref']
                }

            s = Stripe(c, stripe['name'], stripe['rgb'],
                       (stripe['map']['r'], stripe['map']['g'], stripe['map']['b']))

            c.stripes.append(s)
            log.debug("Added stripe %s to controller %s; new len %s", c.id, s.id, len(c.stripes))

            rjson = {
                'success': True,
                'sid': s.id,
                'ref': req_json['ref']
            }

            return json.dumps(rjson)

    @ledd_protocol(protocol)
    def get_stripes(self, req_json):
        """
        Part of the Color API. Used to get all registered stripes known to the daemon.
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
    def test_channel(self, req_json):
        """
        Part of the Color API. Used to test a channel on a specified controller.
        Required JSON parameters: controller id: cid, channel, value
        :param req_json: dict of request json
        """
        log.debug("recieved action: %s", req_json['action'])

        result = next(filter(lambda x: x.id == req_json['cid'], self.controllers), None)
        """ :type : ledd.controller.Controller """

        if result is not None:
            result.set_channel(req_json['channel'], req_json['value'])

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
            try:
                data_split = data.splitlines()
                log.debug(data_split)
                for line in data_split:
                    if line:
                        json_decoded = json.loads(line)

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

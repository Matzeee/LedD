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
import os
import sys
import asyncio
import signal

from sqlalchemy import create_engine
from jsonrpc import JSONRPCResponseManager, dispatcher
from jsonrpc.exceptions import JSONRPCError
import spectra
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound

from ledd import VERSION
from ledd.effectstack import EffectStack
from ledd.models import Meta
from ledd.stripe import Stripe
from ledd.controller import Controller, ControllerEncoder
from . import Base, session

log = logging.getLogger(__name__)

daemonSection = 'daemon'
databaseSection = 'db'
loop = None
""" :type : asyncio.BaseEventLoop """
effects = []


def run():
    try:
        # read config
        config = configparser.ConfigParser()
        try:
            with open('ledd.config', 'w+') as f:
                config.read_file(f)
        except FileNotFoundError:
            log.info("No config file found!")
            pass

        # SQL init
        global engine
        engine = create_engine("sqlite:///" + config.get(databaseSection, 'name', fallback='ledd.sqlite'),
                               echo=log.getEffectiveLevel() == logging.DEBUG)
        session.configure(bind=engine)
        Base.metadata.bind = engine
        if not check_db():
            init_db()

        log.debug(Controller.query.all())
        logging.getLogger("asyncio").setLevel(log.getEffectiveLevel())

        # sigterm handler
        def sigterm_handler():
            raise SystemExit

        signal.signal(signal.SIGTERM, sigterm_handler)

        # init plugins
        # TODO: check all plugins for existing hooks

        # main loop
        global loop
        loop = asyncio.get_event_loop()
        coro = loop.create_server(LedDProtocol,
                                  config.get(daemonSection, 'host', fallback='0.0.0.0'),
                                  config.get(daemonSection, 'port', fallback=1425))
        global server
        server = loop.run_until_complete(coro)
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        log.info("Exiting")
        try:
            os.remove("ledd.pid")
        except FileNotFoundError:
            pass
        # TODO: close engine?
        if server is not None:
            server.close()
        if loop is not None:
            loop.run_until_complete(server.wait_closed())
            loop.close()
        sys.exit(0)


def check_db():
    """
    Checks database version
    :return: database validity
    :rtype: bool
    """
    try:
        db_version = Meta.get_version()

        if db_version is not None:
            log.info("DB connection established; db-version=%s", db_version)
            return True
    except OperationalError:
        return False
    return False


def init_db():
    Base.metadata.drop_all()
    Base.metadata.create_all()
    session.add(Meta(option="db_version", value="2"))
    session.commit()
    check_db()


@dispatcher.add_method
def start_effect(**kwargs):
    """
    Part of the Color API. Used to start a specific effect.
    Required JSON parameters: stripe IDs: sids; effect id: eid, effect options: eopt
    :param req_json: dict of request json
    """

    stripes = []

    if "sids" in kwargs:
        for stripe in Stripe.query.filter(Stripe.id.in_(kwargs['sids'])):
            # TODO: add anything required to start effect with req_json['eid']
            # on stripes[] with options in req_json['eopt']
            effect = EffectStack()
            effects.append(effect)
            effect.stripes.append(stripe)
            effect.start()

            # asyncio.ensure_future(asyncio.get_event_loop().run_in_executor(executor, effect.execute))

            rjson = {
                'eident': None,  # unique effect identifier that identifies excatly this effect started on this set of
                # stripes, used to stop them later and to give informations about running effects
            }

            return rjson
        else:
            return JSONRPCError(-1003, "Stripeid not found")


@dispatcher.add_method
def stop_effect(**kwargs):
    """
    Part of the Color API. Used to stop a specific effect.
    Required JSON parameters: effect identifier: eident
    :param req_json: dict of request json
    """

    # TODO: add stop effect by eident logic


@dispatcher.add_method
def get_effects(**kwargs):
    """
    Part of the Color API. Used to show all available and running effects.
    Required JSON parameters: -
    :param req_json: dict of request json
    """

    # TODO: list all effects here and on which stripes they run atm
    # TODO: all effects get runtime only ids, "eid"'s. They are shown here for the client to start effects.
    # TODO: All options that an effect may have need to be transmitted here too with "eopt".


@dispatcher.add_method
def set_color(**kwargs):
    """
    Part of the Color API. Used to set color of a stripe.
    Required JSON parameters: stripe ID: sid; HSV values hsv: h,s,v, controller id: cid
    :param req_json: dict of request json
    """
    try:
        stripe = Stripe.query.filter(Stripe.id == kwargs['sid']).one()
        stripe.set_color(spectra.hsv(kwargs['hsv']['h'], kwargs['hsv']['s'], kwargs['hsv']['v']))
    except NoResultFound:
        log.warning("Stripe not found: id=%s", kwargs['sid'])


@dispatcher.add_method
def add_controller(**kwargs):
    """
    Part of the Color API. Used to add a controller.
    Required JSON parameters: channels; i2c_dev: number of i2c device (e.g. /dev/i2c-1 would be i2c_dev = 1);
                              address: hexdecimal address of controller on i2c bus, e.g. 0x40
    :param req_json: dict of request json
    """
    try:
        ncontroller = Controller(channels=int(kwargs['channels']), i2c_device=int(kwargs['i2c_dev']),
                                 address=kwargs['address'])
    except OSError as e:
        log.error("Error opening i2c device: %s (%s)", kwargs['i2c_dev'], e)
        return JSONRPCError(-1004, "Error while opening i2c device", e)

    session.add(ncontroller)
    session.commit()

    rjson = {
        'cid': ncontroller.id,
    }

    return rjson


@dispatcher.add_method
def get_color(**kwargs):
    """
    Part of the Color API. Used to get the current color of an stripe.
    Required JSON parameters: stripes
    :param req_json: dict of request json
    """
    try:
        stripe = Stripe.query.filter(Stripe.id == kwargs['sid']).one()
    except NoResultFound:
        log.warning("Stripe not found: id=%s", kwargs['sid'])
        return JSONRPCError(-1003, "Stripeid not found")

    rjson = {
        'color': stripe.color.values,
    }

    return rjson


@dispatcher.add_method
def add_stripe(**kwargs):
    """
    Part of the Color API. Used to add stripes.
    Required JSON parameters: name; rgb: bool; map: r: r-channel, g: g-channel, b: b-channel, cid
    :param req_json: dict of request json
    """

    if "stripe" in kwargs:
        stripe = kwargs['stripe']
        c = Controller.query.filter(Controller.id == int(stripe['cid'])).first()
        """ :type c: ledd.controller.Controller """

        if c is None:
            return JSONRPCError(-1002, "Controller not found")

        s = Stripe(name=stripe['name'], rgb=bool(stripe['rgb']),
                   channel_r=stripe['map']['r'], channel_g=stripe['map']['g'], channel_b=stripe['map']['b'])
        s.controller = c
        log.debug("Added stripe %s to controller %s; new len %s", c.id, s.id, len(c.stripes))

        rjson = {
            'sid': s.id,
        }

        return rjson


@dispatcher.add_method
def get_stripes(**kwargs):
    """
    Part of the Color API. Used to get all registered stripes known to the daemon.
    Required JSON parameters: none
    :param req_json: dict of request json
    """

    rjson = {
        'ccount': len(Controller.query),
        'controller': json.dumps(Controller.query, cls=ControllerEncoder),
    }

    return rjson


@dispatcher.add_method
def test_channel(**kwargs):
    """
    Part of the Color API. Used to test a channel on a specified controller.
    Required JSON parameters: controller id: cid, channel, value
    :param req_json: dict of request json
    """

    result = Controller.query.filter(Controller.id == kwargs['cid']).first()
    """ :type : ledd.controller.Controller """

    if result is not None:
        result.set_channel(kwargs['channel'], kwargs['value'], 2.8)


@dispatcher.add_method
def discover(**kwargs):
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


def find_stripe(sid):
    """
    Deprecated. Use a query instead. Or this should be moved to a classmethod in Stripe
    Finds a given stripeid in the currently known controllers
    :param sid stripe id
    :return: stripe if found or none
    :rtype: ledd.Stripe | None
    """

    return Stripe.query.filter(Stripe.id == sid).first()


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
                    self.transport.write(JSONRPCResponseManager.handle(line, dispatcher).json.encode())

    def connection_lost(self, exc):
        # The socket has been closed, stop the event loop
        # Daemon.loop.stop()
        log.info("Lost connection to %s", self.transport.get_extra_info("peername"))

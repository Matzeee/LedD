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

import asyncio
import configparser
import errno
import logging
import os
import signal
import sys

import spectra
from jsonrpc import JSONRPCResponseManager, dispatcher
from jsonrpc.exceptions import JSONRPCError, JSONRPCInvalidParams
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound

from ledd import VERSION
from ledd.controller import Controller
from ledd.effectstack import EffectStack
from ledd.models import Meta
from ledd.stripe import Stripe
from . import Base, session

log = logging.getLogger(__name__)

daemonSection = 'daemon'
databaseSection = 'db'
""" :type : asyncio.BaseEventLoop """
effects = []
stripes = []
controller = []


def run():
    try:
        # read config
        config = configparser.ConfigParser()
        try:
            with open('ledd.config', 'w+') as f:
                config.read_file(f)
        except FileNotFoundError:
            log.info("No config file found!")

        # SQL init
        global engine
        engine = create_engine("sqlite:///" + config.get(databaseSection, 'name', fallback='ledd.sqlite'),
                               echo=log.getEffectiveLevel() == logging.DEBUG)
        session.configure(bind=engine)
        Base.metadata.bind = engine
        if not check_db():
            init_db()

        logging.getLogger("asyncio").setLevel(log.getEffectiveLevel())

        # Load to cache
        global controller, stripes
        controller = Controller.query.all()

        for c in controller:
            stripes.extend(c.stripes)

        # sigterm handler
        def sigterm_handler():
            raise SystemExit

        signal.signal(signal.SIGTERM, sigterm_handler)

        # init plugins
        # TODO: check all plugins for existing hooks

        # main loop
        global loop, server
        loop = asyncio.get_event_loop()
        coro = loop.create_server(LedDProtocol,
                                  config.get(daemonSection, 'host', fallback='0.0.0.0'),
                                  config.get(daemonSection, 'port', fallback=1425))
        server = loop.run_until_complete(coro)
        log.info("Start phase finished; starting main loop")
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        log.info("Exiting")

        for c in controller:
            c.close()

        try:
            os.remove("ledd.pid")
        except FileNotFoundError:
            pass
        session.commit()
        session.close()
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
            log.info("DB connection established; db_version=%s", db_version)
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
    Required parameters: stripe IDs: sids; effect id: eid, effect options: eopt
    :param kwargs:
    """

    if "sids" not in kwargs or "eid" not in kwargs or "eopt" not in kwargs:
        return JSONRPCInvalidParams()

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

    return JSONRPCError(-1003, "Stripeid not found")


@dispatcher.add_method
def stop_effect(**kwargs):
    """
    Part of the Color API. Used to stop a specific effect.
    Required parameters: effect identifier: eident
    """

    # TODO: add stop effect by eident logic


@dispatcher.add_method
def get_effects(**kwargs):
    """
    Part of the Color API. Used to show all available and running effects.
    Required parameters: -
    """

    # TODO: list all effects here and on which stripes they run atm
    # TODO: all effects get runtime only ids, "eid"'s. They are shown here for the client to start effects.
    # TODO: All options that an effect may have need to be transmitted here too with "eopt".


@dispatcher.add_method
def set_color(**kwargs):
    """
    Part of the Color API. Used to set color of a stripe.
    Required parameters: stripe ID: sid; HSV values hsv: h,s,v, controller id: cid
    """

    if "sid" not in kwargs or "hsv" not in kwargs:
        return JSONRPCInvalidParams()

    stripe = get_stripe(kwargs['sid'])

    if stripe:
        try:
            stripe.set_color(spectra.hsv(kwargs['hsv']['h'], kwargs['hsv']['s'], kwargs['hsv']['v']))
        except OSError as e:
            if int(e) == errno.ECOMM:
                log.warning("Communication error on I2C Bus")
                return e
            else:
                raise
    else:
        log.warning("Stripe not found: id=%s", kwargs['sid'])
        return JSONRPCError(-1003, "Stripeid not found")

    return ""


@dispatcher.add_method
def set_color_all(**kwargs):
    """
    Part of the Color API. Used to set brightness of all stripes a controller owns.
    Required parameters: controller id: cid, value: v
    """

    if "cid" not in kwargs or "v" not in kwargs:
        return JSONRPCInvalidParams()

    try:
        c = get_controller(kwargs['cid'])
        """ :type c: ledd.controller.Controller """

        c.set_all_channel(kwargs['v'])
    except NoResultFound:
        log.warning("Controller not found: id=%s", kwargs['cid'])
        return JSONRPCError(-1002, "Controller not found")

    return ""


@dispatcher.add_method
def add_controller(**kwargs):
    """
    Part of the Color API. Used to add a controller.
    Required parameters: channels; i2c_dev: number of i2c device (e.g. /dev/i2c-1 would be i2c_dev = 1);
                         address: hexdecimal address of controller on i2c bus, e.g. 0x40
    """

    if "i2c_dev" not in kwargs or "channels" not in kwargs or "address" not in kwargs:
        return JSONRPCInvalidParams()

    try:
        ncontroller = Controller(channels=int(kwargs['channels']), i2c_device=int(kwargs['i2c_dev']),
                                 address=kwargs['address'], _pwm_freq=1526)
    except OSError as e:
        log.error("Error opening i2c device: %s (%s)", kwargs['i2c_dev'], e)
        return JSONRPCError(-1004, "Error while opening i2c device", e)

    session.add(ncontroller)
    session.commit()

    controller.append(ncontroller)

    return {'cid': ncontroller.id}


@dispatcher.add_method
def get_color(**kwargs):
    """
    Part of the Color API. Used to get the current color of an stripe.
    Required parameters: sid
    """

    if "sid" not in kwargs:
        return JSONRPCInvalidParams()

    stripe = get_stripe(kwargs['sid'])

    if not stripe:
        log.warning("Stripe not found: id=%s", kwargs['sid'])
        return JSONRPCError(-1003, "Stripeid not found")

    if stripe.color:
        return {'color': stripe.color.values}
    else:
        log.warning("Stripe has no color: id=%s", kwargs['sid'])
        return JSONRPCError(-1009, "Internal Error")


@dispatcher.add_method
def add_stripe(**kwargs):
    """
    Part of the Color API. Used to add stripes.
    Required  parameters: name; rgb: bool; map: r: r-channel, g: g-channel, b: b-channel, cid
    """

    if "name" not in kwargs or "rgb" not in kwargs or "map" not in kwargs or "cid" not in kwargs:
        return JSONRPCInvalidParams()

    c = get_controller(kwargs['cid'])
    """ :type c: ledd.controller.Controller """

    if c is None:
        log.warning("Controller not found: id=%s", kwargs['cid'])
        return JSONRPCError(-1002, "Controller not found")

    s = Stripe(name=kwargs['name'], rgb=bool(kwargs['rgb']),
               channel_r=kwargs['map']['r'], channel_g=kwargs['map']['g'], channel_b=kwargs['map']['b'])
    s.controller = c
    log.debug("Added stripe %s to controller %s; new len %s", s.id, c.id, len(c.stripes))

    session.add(s)
    session.commit()
    stripes.append(s)

    return {'sid': s.id}


@dispatcher.add_method
def get_stripes(**kwargs):
    """
    Part of the Color API. Used to get all registered stripes known to the daemon.
    Required parameters: -
    """

    rjson = {
        'ccount': len(controller),
        'controller': controller
    }

    return rjson


@dispatcher.add_method
def test_channel(**kwargs):
    """
    Part of the Color API. Used to test a channel on a specified controller.
    Required parameters: controller id: cid, channel, value
    """

    if "cid" not in kwargs or "channel" not in kwargs or "value" not in kwargs:
        return JSONRPCInvalidParams()

    contr = get_controller(kwargs['cid'])
    """ :type : ledd.controller.Controller """

    if contr is not None:
        try:
            contr.set_channel(kwargs['channel'], kwargs['value'], 2.8)
        except OSError as e:
            return JSONRPCError(-1009, "Internal Error", e)
    else:
        return JSONRPCError(-1002, "Controller not found")

    return ""


@dispatcher.add_method
def discover(**kwargs):
    """
    Part of the Color API. Used by mobile applications to find the controller.
    Required parameters: -
    """

    return {'version': VERSION}


def get_stripe(sid):
    for s in stripes:
        if s.id == sid:
            return s


def get_controller(cid):
    for c in controller:
        if c.id == cid:
            return c


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
            self.select_task(d_decoded)

    def select_task(self, data):
        if data:
            data_split = data.splitlines()
            for line in data_split:
                if line:
                    try:
                        self.transport.write(JSONRPCResponseManager.handle(line, dispatcher).json.encode())
                    except TypeError as te:
                        log.warning("Can't send response: %s", te)

    def connection_lost(self, exc):
        log.info("Lost connection to %s", self.transport.get_extra_info("peername"))

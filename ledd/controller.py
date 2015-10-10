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

from json import JSONEncoder
import logging
import time

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

import smbus
from ledd.stripe import Stripe
from . import Base

PCA9685_SUBADR1 = 0x2
PCA9685_SUBADR2 = 0x3
PCA9685_SUBADR3 = 0x4

PCA9685_MODE1 = 0x00
PCA9685_MODE2 = 0x01
PCA9685_PRESCALE = 0xFE

LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09

ALLLED_ON_L = 0xFA
ALLLED_ON_H = 0xFB
ALLLED_OFF_L = 0xFC
ALLLED_OFF_H = 0xFD


class Controller(Base):
    __tablename__ = "controller"

    id = Column(Integer, primary_key=True)
    channels = Column(Integer)
    i2c_device = Column(Integer)
    address = Column(String)
    stripes = relationship("Stripe", backref="controller")
    _pwm_freq = Column("pwm_freq", Integer)

    """
    A controller controls a number of stripes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mode = None
        self.bus = smbus.SMBus(self.i2c_device)
        self._address = int(self.address, 16)

    def __repr__(self):
        return "<Controller stripes={} cid={}>".format(len(self.stripes), self.id)

    def set_channel(self, channel, val, gamma):
        self.bus.write_word_data(self._address, LED0_OFF_L + 4 * channel, self.gamma_correct(gamma, int(val * 4095),
                                                                                             4095))
        self.bus.write_word_data(self._address, LED0_ON_L + 4 * channel, 0)

    @staticmethod
    def gamma_correct(gamma, val, maxval):
        corrected = int(pow(float(val) / float(maxval), float(gamma)) * float(maxval) + 0.5)
        logging.getLogger(__name__).debug("GammaCorrect: in=%s out=%s, gamma=%s", val, corrected, gamma)
        return corrected

    def get_channel(self, channel):
        return self.bus.read_word_data(self._address, LED0_OFF_L + 4 * channel) / 4095

    def reset(self):
        self.mode = int("0b00100001", 2)  # MODE1 -> 0b00000001
        time.sleep(0.015)
        self.mode = int("0b10100001", 2)

    @property
    def mode(self):
        self._mode = self.bus.read_byte_data(self._address, PCA9685_MODE1)
        logging.getLogger(__name__).debug("Controller mode: %s", bin(self._mode))
        return self._mode

    @mode.setter
    def mode(self, mode):
        self.bus.write_byte_data(self._address, PCA9685_MODE1, mode)
        self._mode = mode
        logging.getLogger(__name__).debug("Controller mode: %s", bin(self._mode))

    @property
    def pwm_freq(self):
        self._pwm_freq = (self.bus.read_byte_data(self._address, PCA9685_PRESCALE) + 1) / 4096 * 25000000
        return self._pwm_freq

    @pwm_freq.setter
    def pwm_freq(self, value):
        if value < 24 or value > 1526:
            raise ValueError("PWM frequency must be 24Hz <= pwm_freq <= 1526Hz: {}".format(value))
        prescal = round((25000000.0 / (4096.0 * value))) - 1
        logging.getLogger(__name__).debug("Presacle value: %s", prescal)

        self.mode = int("0b00110001", 2)
        self.bus.write_byte_data(self._address, PCA9685_PRESCALE, prescal)
        self.reset()
        self._pwm_freq = value


class ControllerEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Controller):
            return {
                'id': o.id,
                'pwm_freq': o.pwm_freq,
                'channel': o.channels,
                'address': o.address,
                'stripes': o.stripes,
                'cstripes': len(o.stripes),
                'i2c_device': o.i2c_device,
                'mode': o.mode
            }
        elif isinstance(o, Stripe):
            return {
                'id': o.id,
                'name': o.name,
                'rgb': o.rgb,
                'channel': o.channels
            }

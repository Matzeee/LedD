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

from spectra import Color
from sqlalchemy import Integer, ForeignKey, String, Float, Boolean
from sqlalchemy import Column

from . import Base


class Stripe(Base):
    __tablename__ = "stripe"
    """
    A stripe is the smallest controllable unit.
    """
    id = Column(Integer, primary_key=True)
    controller_id = Column(Integer, ForeignKey('controller.id'))
    name = Column(String)
    channel_r = Column(Integer)
    channel_g = Column(Integer)
    channel_b = Column(Integer)
    channel_r_gamma = Column(Float, default=2.8)
    channel_g_gamma = Column(Float, default=2.8)
    channel_b_gamma = Column(Float, default=2.8)
    rgb = Column(Boolean)

    @property
    def channels(self):
        return self.channel_r, self.channel_b, self.channel_g

    # TODO save channels to db

    @channels.setter
    def channels(self, t):
        self.channel_r, self.channel_g, self.channel_b = t

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def read_color(self):
        rc = tuple([float(self.controller.get_channel(channel)) for channel in self.channels])
        c = Color("rgb", rc[0], rc[1], rc[2])
        self._color = c.to("hsv")

    def __repr__(self):
        return "<Stripe id={}>".format(self.id)

    def set_color(self, c):
        self._color = c
        for channel, gamma_correct, value in zip(self.channels, self.gamma_correct, c.clamped_rgb):
            self.controller.set_channel(channel, value, gamma_correct)

    def get_color(self):
        return self._color

    color = property(get_color, set_color)

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


class Stripe:
    """
    A stripe is the smallest controllable unit.
    """

    def __init__(self, controller, name, rgb, channels, sid=-1, gamma_correct=(2.8, 2.8, 2.8), from_db=False):
        self.controller = controller
        self.name = name
        self.rgb = bool(rgb)
        self.channels = channels
        self.id = sid
        self._color = None
        self.gamma_correct = gamma_correct
        self.read_color()
        if not from_db:
            self.save_to_db()

    def save_to_db(self):
        cur = self.controller.db.cursor()
        if self.id == -1:
            cur.execute("INSERT INTO stripes DEFAULT VALUES")
            self.id = cur.lastrowid
        cur.execute(
            "UPDATE stripes SET "
            "channel_r_gamma = ?,"
            "channel_g_gamma = ?,"
            "channel_b_gamma = ?,"
            "channel_r = ?,"
            "channel_g = ?,"
            "channel_b = ?,"
            "controller_id = ?,"
            "name = ? WHERE id = ?",
            self.gamma_correct + self.channels + (self.controller.id, self.name, self.id))
        cur.close()
        self.controller.db.commit()

    def read_color(self):
        rc = tuple([float(self.controller.get_channel(channel)) for channel in self.channels])
        c = Color("rgb", rc[0], rc[1], rc[2])
        self._color = c.to("hsv")

    def __repr__(self):
        return "<Stripe id={}>".format(self.id)

    @classmethod
    def from_db(cls, controller, row):
        return cls(controller, name=row["name"], rgb=row["rgb"],
                   channels=(row["channel_r"], row["channel_g"], row["channel_b"]), sid=row["id"],
                   gamma_correct=(row["channel_r_gamma"], row["channel_g_gamma"], row["channel_b_gamma"]), from_db=True)

    def set_color(self, c):
        self._color = c
        for channel, gamma_correct, value in zip(self.channels, self.gamma_correct, c.clamped_rgb):
            self.controller.set_channel(channel, value, gamma_correct)

    def get_color(self):
        return self._color

    color = property(get_color, set_color)

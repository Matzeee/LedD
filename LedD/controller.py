import smbus
from colour import Color

PCA9685_SUBADR1 = 0x2
PCA9685_SUBADR2 = 0x3
PCA9685_SUBADR3 = 0x4

PCA9685_MODE1 = 0x00
PCA9685_MODE2 = 0x01
PCA9685_PRESCALE = 0xFE
PCA9685_RESET = 0xFE

LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09

ALLLED_ON_L = 0xFA
ALLLED_ON_H = 0xFB
ALLLED_OFF_L = 0xFC
ALLLED_OFF_H = 0xFD




class Controller:
    """
    A controller controls a number of stripes.
    """

    @classmethod
    def from_row(cls, db, row):
        # load from db
        return cls(db, pwm_freq=row["pwm_freq"], channels=row["channels"], i2c_device=row["i2c_device"],
                   address=row["address"], cid=row["id"])

    @staticmethod
    def from_db(db):
        l = []
        cur = db.cursor()
        for row in cur.execute("select * from controller"):
            l.append(Controller.from_row(db, row))
        cur.close()
        return l

    def __init__(self, db, pwm_freq, channels, i2c_device, address, cid=-1):
        self.pwm_freq = pwm_freq
        self.channels = channels
        self.i2c_device = i2c_device
        self.bus = smbus.SMBus(i2c_device)
        self.address = address
        self.id = cid
        self.db = db
        self.stripes = []
        self.load_stripes()

    def load_stripes(self):
        cur = self.db.cursor()
        for stripe in cur.execute("select * from stripes where controller_id = ?", (self.id,)):
            self.stripes.append(Stripe.from_db(self, stripe))

    def __repr__(self):
        return "<Controller stripes={} cid={}>".format(len(self.stripes), self.id)

    def set_channel(self, channel, val):
        self.bus.write_word_data(self.address, LED0_OFF_L + 4 * channel, val*4095)
        self.bus.write_word_data(self.address, LED0_ON_L + 4 * channel, 0)

    def get_channel(self, channel):
        return self.bus.read_word_data(self.address, LED0_OFF_L + 4 * channel)


class Stripe:
    """
    A stripe is the smallest controllable unit.
    """

    def __init__(self, controller, name, rgb, channels):
        self.controller = controller
        self.name = name
        self.rgb = bool(rgb)
        self.channels = channels
        self._color = Color()
        self.gamma_correct = (2.8,2.8,2.8)
        self.read_color()

    def read_color(self):
        self._color.rgb = [self.controller.get_channel(channel)**(1/2.8) for channel in self.channels]

    @classmethod
    def from_db(cls, controller, row):
        return cls(controller, name=row["name"], rgb=row["rgb"], channels=(row["channel_r"],row["channel_g"],row["channel_b"]))

    def set_color(self, c):
        self._color = c
        for channel, gamma_correct, value in zip(self.channels, self.gamma_correct, c.rgb):
            self.controller.set_channel(channel,value**gamma_correct)

    def get_color(self):
        return self._color

    color = property(get_color, set_color)
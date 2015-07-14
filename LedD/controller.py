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


class Stripe:
    """
    A stripe is the smallest controllable unit.
    """

    def __init__(self, controller, name, rgb, channels):
        self.controller = controller
        self.name = name
        self.rgb = bool(rgb)
        self.channels = channels

    @classmethod
    def from_db(cls, controller, row):
        return cls(controller, name=row["name"], rgb=row["rgb"], channels={"r": row["channel_r"],
                                                                           "g": row["channel_g"],
                                                                           "b": row["channel_b"]})

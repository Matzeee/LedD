from pkgutil import iter_modules

if "smbus" not in (name for loader, name, ispkg in iter_modules()):
    print("smbus not found, installing replacement")


    class SMBus:
        def __init__(self, i2c_address):
            self.i2c_address = i2c_address
            self.channels = {}

        def write_word_data(self, cmd, val):
            if (cmd - 6) % 4 == 0:
                self.channels[(cmd - 6) / 4] = val

        def read_word_data(self, cmd):
            return self.channels[(cmd - 8) / 4]


    import sys

    sys.modules['smbus'] = SMBus
import LedD.daemon

if __name__ == "__main__":
    daemon = LedD.daemon.Daemon()

# LedD

LedD is a daemon for interfacing LED stripes written in python3. It provides an abstract interface for effects to control any kind of LED stripe through an controller, although it is intented to be used with the PCA9685 chip. An Android application can connect and natively change any settings for the effects and stripes.

## Goals

- manage multiple stripes and controllers at the same time
- an open effects github repository with simple download-and-run system
- automatic enumeration of the connected controller devices, restart/reset and status querys

## Requirements

- Python 3.x, tested with Python 3.4
- Linux with i2c-dev module loaded and permissions to access /dev/i2c-* devices, preferably as non-root (add your user to the i2c group)
- Compatible controller device connected via i2c; currently supported controllers:
    - PCA9685
- __Note__: Plugins can have different permission requirements

### Plugins & Effects

Plugin functionality is planned as we provide APIs for effects and plugins to use. Here are some we are going to provide when they are finished.

Plugins
- lux sensor (TSL2591) for providing information if lights need to be turned on
- start/stop hook so you can switch your LED power supply
- planned hook points for plugins include
    - start/stop
    - set color (for e.g. gamma correction)
- controller support

Effects
- pulse
- fade
- drop
- blink
- strobe (as far as possible)
    
#### License

This project is licensed under the conditions of the GNU GPL 3.0.

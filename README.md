# LedD

LedD is a daemon for interfacing LED stripes written in python3. It provides an abstract interface for effects to control any kind of LED stripe through an controller, although it is intented to be used with the PCA9685 chip. An Android application can connect and natively change any settings for the effects and stripes.

## Goals

- manage multiple stripes and controllers at the same time
- an open effects github repository with simple download-and-run system
- automatic enumeration of the connected controller devices, restart/reset and status querys

### License

This project is licensed under the conditions of the GNU GPL 3.0.

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

from setuptools import setup

setup(name='LedD',
      version='0.1',
      description='Providing control for led stripes.',
      url='https://github.com/LED-Freaks/LedD',
      author='IdleGandalf, Lauch',
      author_email='ledd@idlegandalf.com',
      license='GPLv3',
      packages=['ledd'],
      install_requires=[
            'nose', 'spectra', 'docopt', 'jsonrpc',
      ],
      zip_safe=False)

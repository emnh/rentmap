#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ft=python ts=4 sw=4 sts=4 et fenc=utf-8
# Original author: "Eivind Magnus Hvidevold" <hvidevold@gmail.com>
# License: GNU GPLv3 at http://www.gnu.org/licenses/gpl.html

'''
'''

import os
import sys
import re
from google.appengine.api import datastore_types

def encode(x):
    value = x.encode('utf-8')
    return datastore_types.Blob(value)

def decode(x):
    return x.decode('utf-8')

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

from google.appengine.ext import db

class AppSettings(db.Model):
    geo_enabled = db.BooleanProperty()

class GlobalSettings(object):

    @staticmethod
    def getSettings():
        settings = AppSettings.get_by_key_name("global")
        if settings is None:
            settings = AppSettings(key_name="global")
            settings.geo_enabled = True
            settings.put()
        return settings

    def __setattr__(self, key, value):
        def helper():
            settings = self.getSettings()
            setattr(settings, key, value)
            settings.put()
        db.run_in_transaction(helper)

    def __getattr__(self, key):
        settings = self.getSettings()
        return getattr(settings, key)

settings = GlobalSettings()

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
import urllib
import urllib2
import datetime
import logging
import time
import app

from django.utils import simplejson as json

from hybel import ApartmentAd, \
    ApartmentEncoder, updateFromHybelNo, \
    DirectionsCache, JsonListings, devReparse

from pprint import pprint, pformat
from BeautifulSoup import BeautifulSoup, NavigableString
from google.appengine.ext import webapp
try:
    from google.appengine.ext import deferred
except:
    pass
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

DEV = os.environ['SERVER_SOFTWARE'].startswith('Development')

class MainPage(webapp.RequestHandler):
    def get(self):
        self.redirect('/static/map.html')


class DirectionsDebug(webapp.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'

        for cache in DirectionsCache.all():
            try:
                self.response.out.write(cache.key().name().encode('utf-8'))
            except:
                self.response.out.write('FAIL')
            self.response.out.write(cache.json_content)
            self.response.out.write('\n\n')

class ListingsDebug(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'

        for ad in ApartmentAd.all():
            json = ApartmentEncoder().encode(ad)
            self.response.out.write(json)
            self.response.out.write(ad.html_content)
            self.response.out.write('\n\n')


# TODO: memcache
class ApartmentListings(webapp.RequestHandler):

    def get(self):
        #self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Content-Type'] = 'text/javascript'
        outfd = self.response.out
        outfd.write('function getListings() {\n')
        outfd.write('return ')
        outfd.write(JsonListings.get())
        outfd.write(';\n')
        outfd.write('}\n')


class InvalidateApartmentListings(webapp.RequestHandler):

    def get(self):
        JsonListings.invalidate()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Invalidated JSON cache')

class UpdatePage(webapp.RequestHandler):
    def get(self):
        deferred.defer(updateFromHybelNo)
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Update scheduled')

class EnableGeocoding(webapp.RequestHandler):
    def get(self):
        app.settings.geo_enabled = True
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Geocoding enabled')

class DevReparse(webapp.RequestHandler):
    def get(self):
        deferred.defer(devReparse)
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Reparse scheduled')

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/listings', ListingsDebug),
                                      ('/directions_cache', DirectionsDebug),
                                      ('/listings.js', ApartmentListings),
                                      ('/dev_reparse', DevReparse),
                                      ('/invalidate-listings', InvalidateApartmentListings),
                                      ('/update', UpdatePage),
                                      ('/enable_geocoding', EnableGeocoding)
                                     ],
                                     debug=True)

def main():
    if DEV:
        #logging.basicConfig(filename='/home/emh/rentmap.log',level=logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

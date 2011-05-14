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
import parse
import datetime
import json
import logging
import time
from hybel import ApartmentAd, ApartmentEncoder, updateFromHybelNo

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

        ads = [ad for ad in ApartmentAd.all()]
        json = ApartmentEncoder().encode(ads)

        outfd = self.response.out
        outfd.write('function getListings() {\n')
        outfd.write('return ')
        outfd.write(json)
        outfd.write(';\n')
        outfd.write('}\n')


class UpdatePage(webapp.RequestHandler):
    def get(self):
        #deferred.defer(updateFromHybelNo)
        updateFromHybelNo()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Update scheduled')

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/listings', ListingsDebug),
                                      ('/listings.js', ApartmentListings),
                                      ('/update', UpdatePage)
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

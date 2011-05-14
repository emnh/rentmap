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
import urllib2
import parse
import datetime
import json

from pprint import pprint, pformat
from BeautifulSoup import BeautifulSoup, NavigableString
from google.appengine.ext import webapp
from google.appengine.ext import deferred
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

class ApartmentAd(db.Model):
    address = db.PostalAddressProperty()
    apartment_type = db.StringProperty()
    created = db.DateProperty()
    html_content = db.BlobProperty()
    listing_text = db.TextProperty()
    url = db.LinkProperty()
    image = db.LinkProperty()
    has_image = db.BooleanProperty()
    price = db.IntegerProperty()
    latlng = db.GeoPtProperty()

SIMPLE_TYPES = (int, long, float, bool, dict, basestring, list)
def modelToDict(model):
    output = {}

    for key, prop in model.properties().iteritems():
        value = getattr(model, key)

        if value is None or isinstance(value, SIMPLE_TYPES):
            output[key] = value
        elif isinstance(value, datetime.date):
            # Convert date/datetime to ms-since-epoch ("new Date()").
            #ms = time.mktime(value.utctimetuple()) * 1000
            #ms += getattr(value, 'microseconds', 0) / 1000
            #output[key] = int(ms)
            output[key] = value.isoformat()
        elif isinstance(value, db.GeoPt):
            output[key] = {'lat': value.lat, 'lon': value.lon}
        elif isinstance(value, db.Model):
            output[key] = to_dict(value)
        else:
            raise ValueError('cannot encode ' + repr(prop))

    return output

class ApartmentEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ApartmentAd):
            return modelToDict(obj)
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class HybelNoParser(object):

    BaseURL = 'http://hybel.no'

    @staticmethod
    def parseAddress(souphouse):
        addr = souphouse.find('div', 'address')
        lines = [x.strip() for x in addr if isinstance(x, NavigableString)]
        return lines

    @staticmethod
    def parseApartmentAd(souphouse):
        ad_id = souphouse['id']
        h = ApartmentAd(key_name=ad_id)
        image = souphouse.find('img')
        if image != -1:
            h.image = HybelNoParser.BaseURL + image['src']
            h.has_image = (image['src'] != '/images/default.png')
        else:
            raise Exception('No img tag found')
        link = souphouse.find('div', 'listing-text').h3.a
        h.listing_text = link.string
        h.url = HybelNoParser.BaseURL + link['href']
        h.price = int(souphouse.find('div', 'price').strong.string.replace(',-', ''))
        address = HybelNoParser.parseAddress(souphouse)
        if address[1] == '' and address[2] == '':
            h.address = None
        elif address[1] == '' and address[2] != '':
            h.lookup_address = ','.join(address[0:3:2])
        else:
            h.lookup_address = ','.join(address[1:3])
        h.apartment_type = str(souphouse.find('div', 'house').strong.string)
        date = souphouse.find('div', 'created').string.strip()
        h.created = datetime.datetime.strptime(date, '%d.%m.%Y').date()
        return h

    @staticmethod
    def getApartmentAds(pagedata):
        soup = BeautifulSoup(pagedata, convertEntities=BeautifulSoup.ALL_ENTITIES)
        listings = soup.find('ul', 'ad-list')
        for souphouse in listings.findAll('li', 'ad-list-entry'):
            yield souphouse

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'

        for ad in ApartmentAd.all():
            json = ApartmentEncoder().encode(ad)
            self.response.out.write(json)
            self.response.out.write('\n\n')


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
        url = 'http://www.hybel.no/bolig-til-leie/annonser/oslo?side=1'
        data = memcache.get(url)
        if data is None:
            fd = urllib2.urlopen(url)
            data = fd.read()
            fd.close()
            memcache.add(url, data, 300)

        self.response.headers['Content-Type'] = 'text/plain'
        for soup_ad in HybelNoParser.getApartmentAds(data):
            ad = HybelNoParser.parseApartmentAd(soup_ad)
            ad.put()

        self.response.out.write('Update complete')

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/listings.js', ApartmentListings),
                                      ('/update', UpdatePage)
                                     ],
                                     debug=True)

class UpdateWorker(webapp.RequestHandler):
    def post(self): # should run at most 1/s
        key = self.request.get('key')
        def txn():
            counter = Counter.get_by_key_name(key)
            if counter is None:
                counter = Counter(key_name=key, count=1)
            else:
                counter.count += 1
            counter.put()
        db.run_in_transaction(txn)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

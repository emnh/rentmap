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

from pprint import pprint, pformat
from BeautifulSoup import BeautifulSoup, NavigableString
from google.appengine.ext import webapp
from google.appengine.ext import deferred
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.runtime import DeadlineExceededError

SIMPLE_TYPES = (int, long, float, bool, dict, basestring, list)
DESTINATION = 'Torggata 2, Oslo'
DEV = os.environ['SERVER_SOFTWARE'].startswith('Development')
CITY = 'Oslo'
ADDRESS_WHITESPACE = '\t\r\n ,'

class OverLimitException(Exception):
    pass

class ApartmentAd(db.Model):
    address = db.PostalAddressProperty()
    address_urlquoted = db.PostalAddressProperty()
    apartment_type = db.StringProperty()
    created = db.DateProperty()
    has_image = db.BooleanProperty()
    html_content = db.BlobProperty()
    image = db.LinkProperty()
    listing_text = db.TextProperty()
    price = db.IntegerProperty()
    url = db.LinkProperty()

    # geo properties
    latlng = db.GeoPtProperty()
    geocode_status = db.StringProperty()
    distance_text = db.StringProperty()
    distance_value = db.IntegerProperty()
    duration_text = db.StringProperty()
    duration_value = db.IntegerProperty()

    # list of remaining tasks
    tasks = db.StringListProperty()

    def addTask(self, taskname):
        if not taskname in self.tasks:
            self.tasks.append(taskname)

    def removeTask(self, taskname):
        if taskname in self.tasks:
            self.tasks.remove(taskname)

    def parse(self):
        logging.info("Parsing ad with id %s" % self.key().name())
        soup_ad = BeautifulSoup(self.html_content, convertEntities=BeautifulSoup.ALL_ENTITIES)
        ad = HybelNoParser.parseApartmentAd(self, soup_ad)
        #ad.dirCode(DESTINATION)
        self.removeTask('parse')
        self.addTask('geocode')
        ad.putAndInvalidateCache()

    def dirCode(self, destination_address):
        if app.settings.geo_enabled:
            logging.info("GeoCoding ad with id %s" % self.key().name())
        else:
            logging.info("GeoCoding disabled, postponing geocoding of ad with id %s" % self.key().name())
            return
        success = False
        # TODO: maybe write field with direction lookup result status: 
        # no address, no match, perhaps propagate returned lookup status
        if self.address:
            origin = self.address_urlquoted
            # TODO: parameterize
            if not CITY.lower() in origin.lower():
                origin += ', ' + CITY

            data = None
            try:
                data = GeoCoder.dirCode(origin, destination_address)
            except OverLimitException:
                app.settings.geo_enabled = False
                logging.info("Geo went over limit on ad with id %s, disabling geo coding." % self.key().name())
                self.geocode_status = 'Geo API over limit'
                self.putAndInvalidateCache()
                return

            if data:
                self.geocode_status = 'Google found no directions'
                if len(data['routes']) > 0:
                    leg = data['routes'][0]['legs'][0]
                    self.duration_text = leg['duration']['text']
                    self.duration_value = leg['duration']['value']
                    self.distance_text = leg['distance']['text']
                    self.distance_value = leg['distance']['value']
                    self.latlng = db.GeoPt(
                            leg['start_location']['lat'],
                            leg['start_location']['lng']
                            )
                    self.geocode_status = 'Success'
                    success = True
        else:
            self.geocode_status = 'No address'
        self.removeTask('geocode')
        self.putAndInvalidateCache()
        return success

    def putAndInvalidateCache(self):
        JsonListings.invalidate()
        self.put()

class DirectionsCache(db.Model):
    json_content = db.BlobProperty()

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
            output[key] = {'lat': value.lat, 'lng': value.lon}
        elif isinstance(value, db.Model):
            output[key] = modelToDict(value)
        else:
            raise ValueError('cannot encode ' + repr(prop))

    return output

class ApartmentEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ApartmentAd):
            dict_ = modelToDict(obj)
            del dict_['html_content']
            del dict_['tasks']
            return dict_
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class GeoCoder(object):

    @staticmethod
    def geocodeURL(address):
        address = urllib.quo_namete_plus(address.encode('utf-8'))
        url = 'http://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false' % address
        return url

    @staticmethod
    def directionsURL(start_address, destination_address):
        #origin = urllib.quote_plus(start_address.encode('utf-8'))
        origin = start_address
        destination = urllib.quote_plus(destination_address.encode('utf-8'))
        url = 'http://maps.googleapis.com/maps/api/directions/json?origin=%s&destination=%s&mode=walking&sensor=false' \
                % (origin, destination)
        return url

    @staticmethod
    def cachedRequest(cache_model, url):
        # if cached
        cached_data = cache_model.get_by_key_name(url)
        if cached_data:
            logging.info('Read cached URL: %s' % url)
        else:
            logging.info('Downloading URL: %s' % url)
            fd = urllib.urlopen(url)
            data = fd.read()
            fd.close()
            cached_data = cache_model(key_name = url, json_content = data)
            if not 'OVER_QUERY_LIMIT' in data:
                cached_data.put()
            # TODO: parallel rate limiting
            time.sleep(1)

        return cached_data.json_content

    'Return None if fail, request data otherwise'
    @staticmethod
    def dirCode(apartment_address, destination_address):
        url = GeoCoder.directionsURL(apartment_address, destination_address)
        if url:
            data = GeoCoder.cachedRequest(DirectionsCache, url)
            data = json.loads(data)
            if data['status'] == 'OVER_QUERY_LIMIT':
                msg = "Over query limit, query: %s" % url
                logging.error(msg)
                raise OverLimitException(msg)
            return data

class HybelNoParser(object):

    BaseURL = 'http://hybel.no'

    @staticmethod
    def parseAddress(souphouse):
        url = souphouse.find('a', 'map-gulesider')['href']
        if url:
            match = re.search(r'geo_area=(.*)&sourceid', url)
            if match:
                return match.group(1)

    @staticmethod
    def parseAddress2(souphouse):
        addr = souphouse.find('div', 'address')
        address = [x.strip(ADDRESS_WHITESPACE) for x in addr if isinstance(x, NavigableString)]
        address = [x for x in address if x != '']
#        if address[1] == '' and address[2] == '':
#            address = None
#        elif address[1] == '' and address[2] != '':
#            address = ','.join(address[0:3:2])
#        else:
#            address = ','.join(address[1:3])
        return u', '.join(address)

    @staticmethod
    def parseApartmentAd(h, souphouse):
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
        address_urlquoted = HybelNoParser.parseAddress(souphouse)
        address = urllib.unquote_plus(address_urlquoted).strip(ADDRESS_WHITESPACE)
        # ? address = address.decode('utf-8')
        if not address:
            address = HybelNoParser.parseAddress2(souphouse)
            if address:
                address_urlquoted = urllib.quote_plus(address.encode('utf-8'))
        if address:
            h.address = address
            h.address_urlquoted = address_urlquoted
        else:
            del h.address
            del h.address_urlquoted
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

class JsonListings(object):

    cacheName = 'listings-json'

    @staticmethod
    def invalidate():
        memcache.delete(JsonListings.cacheName)

    @staticmethod
    def get():
        json = memcache.get(JsonListings.cacheName)
        if json is None:
            ads = [ad for ad in ApartmentAd.all()]
            json = ApartmentEncoder().encode(ads)
            memcache.set(JsonListings.cacheName, json)
        return json

def updateFromHybelNo(page=1):
    logging.info("Starting update from hybel.no")
    url_pattern = 'http://www.hybel.no/bolig-til-leie/annonser/oslo?side=%d'
    url = url_pattern % page
    data = memcache.get(url)
    if data is None:
        logging.info("Retrieving hybel page URL: %s" % url)
        fd = urllib2.urlopen(url)
        data = fd.read()
        fd.close()
        memcache.add(url, data, 300)

    # get only new
    new_count = 0
    load_next_page = True
    for soup_ad in HybelNoParser.getApartmentAds(data):
        logging.info("Processing ad with id %s" % soup_ad['id'])
        ap_id = soup_ad['id']
        h = ApartmentAd.get_by_key_name(ap_id)
        if h is None:
            h = ApartmentAd(key_name=ap_id)
            h.html_content = soup_ad.renderContents()
            h.tasks.append('parse')
            h.put()
            new_count += 1
        else:
            # assume we have processed everything after first ad we have seen before, 
            # so we can stop now
            logging.info("Stopping at previously seen ad with id %s" % soup_ad['id'])
            load_next_page = False
            break

    if new_count > 0:
        deferred.defer(parseAllAds)

    if load_next_page and page < 1000: # extra sanity check to avoid infinite recursion
        deferred.defer(updateFromHybelNo, page + 1)

def devReparse():
    for h in ApartmentAd.all():
        if not h.address or h.address.strip(ADDRESS_WHITESPACE) == '':
            h.addTask('parse')
            h.put()
    deferred.defer(parseAllAds)

def parseAllAds():
    try:
        for h in ApartmentAd.all().filter("tasks =", "parse"):
            h.parse()
    except DeadlineExceededError:
        deferred.defer(parseAllAds)
    deferred.defer(geocodeAllAds)

def geocodeAllAds():
    try:
        for h in ApartmentAd.all().filter("tasks =", "geocode"):
            h.dirCode(DESTINATION)
    except DeadlineExceededError:
        deferred.defer(geocodeAllAds)


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
#import locale
from BeautifulSoup import BeautifulSoup, NavigableString
from pprint import pprint, pformat
import inspect
import json
from SimpleHTTPServer import SimpleHTTPRequestHandler
import SocketServer
import traceback
import urllib
import hashlib
import time

#locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

GEODIR = 'geocoding'
DIRECTIONSDIR = 'directions'
BASE = 'http://hybel.no'
PAGEDIR = 'pages'
ENC = 'utf-8'
JSONOUT = 'listings.js'
DESTINATION = 'Torggata 2, Oslo'

#class ChattyType(type):
#    def __new__(cls, name, bases, dct):
#        print "Allocating memory for class", name
#        return type.__new__(cls, name, bases, dct)
#    def __init__(cls, name, bases, dct):
#        print "Init'ing (configuring) class", name
#        super(ChattyType, cls).__init__(name, bases, dct)

#__metaclass__ = ChattyType


class House(object):

    def __str__(self):
        return pformat(self.__dict__) #unicode(self.__dict__).encode(ENC)

    def __repr__(self):
        return str(self)

class HouseEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, House):
            return obj.__dict__
        return json.JSONEncoder.default(self, obj)

#def utfWrapMethod(method):
#    def wrapper(*args):
#        return utfWrapObject(method(*args))
#    return wrapper

#def utfWrapObject(obj):
#    if inspect.isfunction(obj) or inspect.ismethod(obj):
#        return utfWrapMethod(obj)
#    elif isinstance(obj, unicode):
#        return obj.encode('utf-8')
#    elif isinstance(obj, str):
#        return obj
#    else:
#        for name, method in inspect.getmembers(obj, inspect.ismethod):
#            print name
#            obj.setattr(name, utfWrapMethod(method))
#a = u'heøæå'
#utfWrapObject(a)
#print a
#sys.exit()

#class UTF8Adapter(object):
#    '''Wrap an object such that any method that normally returns a unicode string
#    returns it as a string encoded in UTF-8'''

#    def __init__(self, _wrappedObject):
#        self._wrappedObject = wrappedObject

#    def __getattribute__(self, attr):
#        if attr == '_wrappedObject':
#            return self._wrappedObject
#        else:
#            return getattr(self._wrappedObject

def parseaddr(souphouse):
    addr = souphouse.find('div', 'address')
    lines = [x.strip() for x in addr if isinstance(x, NavigableString)]
    return lines

def parsehouse(souphouse):
    h = House()
    image = souphouse.find('img')
    if image != -1:
        h.image = image['src']
        h.hasImage = (image['src'] != '/images/default.png')
    else:
        raise Exception('No img tag found')
    link = souphouse.find('div', 'listing-text').h3.a
    h.listing_text = link.string
    h.href = BASE + link['href']
    h.price = int(souphouse.find('div', 'price').strong.string.replace(',-', ''))
    h.address = parseaddr(souphouse)
    if h.address[1] == '' and h.address[2] == '':
        h.lookup_address = None
    elif h.address[1] == '' and h.address[2] != '':
        h.lookup_address = ','.join(h.address[0:3:2])
    else:
        h.lookup_address = ','.join(h.address[1:3])
    h.housetype = souphouse.find('div', 'house').strong.string
    h.created = souphouse.find('div', 'created').string.strip()
    return h

def wrapRepr(orig):
    def wrapper(arg):
#        print 'REPR', arg.__class__, unicode(arg).encode('utf-8')
#       if instanceof(arg
        return unicode(arg).encode(ENC)
        #return orig(arg)
    return wrapper

#__builtins__.repr = wrapRepr(repr)

def parse(data):
    soup = BeautifulSoup(data, convertEntities=BeautifulSoup.ALL_ENTITIES)
    houses = []
    listings = soup.find('ul', 'ad-list')
    for souphouse in listings.findAll('li', 'ad-list-entry'):
        h = parsehouse(souphouse)
        houses.append(h)
    return houses

def getListings():
    houses = []
    for fname in os.listdir(PAGEDIR):
        fname = os.path.join(PAGEDIR, fname)
        with file(fname) as fd:
            data = fd.read()
            if 'html' in data.splitlines()[0]:
                houses.extend(parse(data))
            else:
                print('skipping', fname)
    return houses

def geocodeURL(address):
    address = urllib.quote_plus(address.encode('utf-8'))
    url = 'http://maps.googleapis.com/maps/api/geocode/json?address=%s&sensor=false' % address
    return url

def directionsURL(address):
    origin = urllib.quote_plus(address.encode('utf-8'))
    destination = urllib.quote_plus(DESTINATION.encode('utf-8'))
    url = 'http://maps.googleapis.com/maps/api/directions/json?origin=%s&destination=%s&mode=walking&sensor=false' \
            % (origin, destination)
    return url

def cachedRequest(dirname, url):
    if not os.path.exists(dirname):
        os.mkdir(dirname)
    fname = hashlib.sha1(url).hexdigest() + '.json'
    fname = os.path.join(dirname, fname)

    # if cached
    if os.path.exists(fname):
        print 'cached', url, fname
        with file(fname) as fd:
            data = fd.read()
    else:
        print 'downloading', url
        fd = urllib.urlopen(url)
        data = fd.read()
        fd.close()
        with file(fname, 'w') as outfd:
            outfd.write(data)
        time.sleep(1)

    return data

def geocode(listings):
    count = 0
    for house in listings:
        if house.lookup_address:
# don't need to to geocoding separately because we get same info from directions
#            url = geocodeURL(house.lookup_address)
#            if url:
#                data = cachedRequest(GEODIR, url)
#                data = json.loads(data)
#                if len(data['results']) > 0:
#                    house.latlng = data['results'][0]['geometry']['location']

            url = directionsURL(house.lookup_address)
            if url:
                data = cachedRequest(DIRECTIONSDIR, url)
                data = json.loads(data)
                #print house.address
                #pprint(data)
                if data['status'] == 'OVER_QUERY_LIMIT':
                    print 'OVER_QUERY_LIMIT!'
                    sys.exit(1)
                if len(data['routes']) > 0:
                    leg = data['routes'][0]['legs'][0]
                    house.duration = leg['duration']
                    house.distance = leg['distance']
                    house.latlng = leg['start_location']
                    count += 1
                #print house
    print 'COUNT', count

def writeHouses(houses, outfd):
    outfd.write('function getListings() {\n')
    outfd.write('return ')
    outfd.write(HouseEncoder().encode(houses))
    outfd.write(';\n')
    outfd.write('}\n')

class MyHandler(SimpleHTTPRequestHandler):

    def do_GET(self):

        print 'GET'
        #print(self.headers)

        houses = getListings()

        ex = None

        try:
            ret = 'helo'
            if self.path == '/listings.js':
                self.send_response(200)
                self.end_headers()
                writeHouses(houses, self.wfile)
            elif self.path.endswith('.html'):
                fname = os.path.basename(self.path)
                if os.path.exists(fname):
                    self.send_response(200)
                    self.end_headers()
                    with file(fname) as fd:
                        self.wfile.write(fd.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write('Page not found')
        except Exception as e:
            if 'abort' in str(e):
                raise
            else:
                ex = traceback.format_exc()
        if ex:
            print(ex)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(ex).encode('utf-8'))

        self.wfile.close()


def run(handler_class=SimpleHTTPRequestHandler):
    server_address = ('', 8000)
    httpd = SocketServer.TCPServer(server_address, handler_class)
    try:
        httpd.serve_forever()
    except:
        httpd.server_close()
        raise
    finally:
        httpd.server_close()

def main():
    'entry point'
    if len(sys.argv) < 1:
        sys.exit(1)
    #run(MyHandler)
    houses = getListings()
    print len(houses)
    geocode(houses)
    # filter
    houses = [x for x in houses if x.hasImage and hasattr(x, 'latlng')]
    with file(JSONOUT, 'w') as outfd:
        writeHouses(houses, outfd)
    print len(houses)
    #pprint(houses)

if __name__ == '__main__':
    main()


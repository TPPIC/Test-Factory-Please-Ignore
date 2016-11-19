#!/usr/bin/env nix-shell
#!nix-shell -i python -p python pythonPackages.beautifulsoup pythonPackages.lxml pythonPackages.futures pythonPackages.progressbar
#
# This autogenerates .json-manifest files from the .json input file(s).

from concurrent.futures import ThreadPoolExecutor
from glob import glob
from HTMLParser import HTMLParser
from lxml.html import soupparser
import json
import os
import re
import sys
import threading
import urllib2
import progressbar
import hashlib

# No. of concurrent HTTP connections.
MAX_CONCURRENCY = 1
http_sem = threading.Semaphore(MAX_CONCURRENCY)
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY*10)
pbar = None
pbar_lock = threading.Lock()

FILENAME = 'filename'
HASH = 'md5'
PROJECTID = 'projectID'
SRC = 'src'

CAFILE = '/etc/ssl/certs/ca-bundle.crt'
if not os.path.isfile(CAFILE):
    CAFILE = os.environ['HOME'] + '/.nix-profile/etc/ssl/certs/ca-bundle.crt'
if not os.path.isfile(CAFILE):
    print 'No ca-bundle.crt found. Try "nix-env -i nss-cacert".'
    quit()


def urlopen(*args, **kwargs):
    return urllib2.urlopen(*args, cafile=CAFILE)

def Get(url):
    with http_sem:
        # print >> sys.stderr, 'Fetching', url
        req = None
        try:
            req = urlopen(url)
            return req.read()
        finally:
            req and req.close()

def DerefUrl(url):
    with http_sem:
        req = None
        try:
            req = urlopen(url)
            return req.geturl()
        finally:
            req and req.close()


def GetNewestVersions(mods):
    baseUrl = 'https://minecraft.curseforge.com'

    def ModData(name):
        mod = mods[name]
        if SRC in mod:
            # This is a non-Curse mod.
            data = GetNonCurseData(name, mod)
        else:
            data = GetNewestCurseData(name, mod)
        for k in mod:
            if k[0] != '_':
                data[k] = mod[k]
        if not (data[FILENAME].endswith('.jar') or data[FILENAME].endswith('.zip')):
            data[FILENAME] += '.jar'
        with pbar_lock:
            pbar.update(pbar.currval + 1)
        return (name, data)

    def GetNonCurseData(name, mod):
        jar = Get(mod[SRC])
        return {
            HASH: hashlib.new(HASH, jar).hexdigest(),
            FILENAME: mod[SRC].split('/')[-1]
        }

    def GetNewestCurseData(name, mod):
        parser = HTMLParser()
        # Name the project.
        projectUrl = baseUrl + '/projects/' + str(name)
        projectUrl = DerefUrl(projectUrl).split('?')[0]
        # Find the project ID.
        projectPage = Get(projectUrl)
        tree = soupparser.fromstring(projectPage)
        projectID = int(tree.xpath('//li[@class="view-on-curse"]/a/@href')[0].split('/')[-1])
        # Find the newest copy of the mod.
        # TODO: Filter by stability, regex, whatever. Add once needed.
        filesUrl = projectUrl + '/files?filter-game-version=2020709689%3A6170'
        filesPage = Get(filesUrl)
        tree = soupparser.fromstring(filesPage)
        files = tree.xpath('//div[@class="project-file-name-container"]/a[@class="overflow-tip"]/@href')
        names = tree.xpath('//div[@class="project-file-name-container"]/a[@class="overflow-tip"]/text()')
        if files:
          # Find the URL and MD5 of that file.
          filePage = Get(baseUrl + files[0])
          tree = soupparser.fromstring(filePage)
          hash = tree.xpath('//span[@class="%s"]/text()' % HASH)
          url = tree.xpath('//a[@class="button fa-icon-download"]/@href')
          return {
              HASH: hash[0],
              SRC: baseUrl + url[0],
              FILENAME: parser.unescape(names[0]),
              PROJECTID: projectID,
          }

    return executor.map(ModData, sorted(mods))


# Go to the directory this file is in.
os.chdir(os.path.dirname(os.path.realpath(__file__)))
# And just... do everything.
mods = {}  # Map from filename to list of mods.
for fn in glob('*.json'):
    mods[fn] = json.load(open(fn))
pbar = progressbar.ProgressBar(
    widgets=['', ' ', progressbar.Percentage(), progressbar.Bar(), progressbar.ETA()],
    maxval=sum(map(len, mods))).start()
for fn, mods in mods.iteritems():
    pbar.widgets[0] = fn
    out = {}
    for name, data in GetNewestVersions(mods):
        out[name] = data
    with open(fn + '-manifest', 'w') as manifest:
        json.dump(out, manifest, indent=2)
pbar.finish()

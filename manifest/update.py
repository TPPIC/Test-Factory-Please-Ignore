#!/usr/bin/env nix-shell
#!nix-shell -i python -p python pythonPackages.beautifulsoup pythonPackages.lxml pythonPackages.futures pythonPackages.progressbar
#
# This autogenerates .json-manifest files from the .json input file(s).

from concurrent.futures import ThreadPoolExecutor
from glob import glob
from HTMLParser import HTMLParser
from lxml.html import soupparser
import hashlib
import json
import os
import progressbar
import re
import sys
import threading
import urllib2
import urlparse

# No. of concurrent HTTP connections.
MAX_CONCURRENCY = 1
http_sem = threading.Semaphore(MAX_CONCURRENCY)
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY*10)
pbar = None
pbar_lock = threading.Lock()

COMMENT = 'comment'
FILENAME = 'filename'
HASH = 'md5'
PROJECTID = 'projectID'
PROJECTPAGE = 'projectPage'
SRC = 'src'
TITLE = 'title'
VERSION = 'version'

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


def ParseVersion(filename):
    """Attempt to extract the version number from the filename.

    Not great. Would be easier and more reliable to use mcmod.info, but then
    we'd need to download the mod file every time.
    """
    match = re.search('[0-9].*', filename)
    return '.'.join((match.group(0) if match else filename).split('.')[0:-1])


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
        if not VERSION in data:
            data[VERSION] = ParseVersion(data[FILENAME])
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
        projectTitle = tree.xpath('//h1[@class="project-title"]//span/text()')[0]
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
              FILENAME: parser.unescape(names[0]),
              HASH: hash[0],
              PROJECTID: projectID,
              PROJECTPAGE: projectUrl,
              SRC: baseUrl + url[0],
              TITLE: projectTitle,
          }

    return executor.map(ModData, sorted(mods))


def GenerateModList(data):
    lines = ['# Mods']
    for filename in sorted(data):
        mods = data[filename]
        lines.append('## %s:' % filename)
        for name in sorted(mods):
            mod = mods[name]
            lines.append('- [%s](%s): %s' % (
                mod.get(TITLE) or name,
                mod.get(PROJECTPAGE) or urlparse.urljoin(mod[SRC], '/'),
                mod.get(VERSION)))
            if COMMENT in mod:
                lines.append('')
                lines.append('  ' + mod[COMMENT])
        lines.append('')
    return '\n'.join(lines)


# Go to the directory this file is in.
os.chdir(os.path.dirname(os.path.realpath(__file__)))
# Find manifests to construct:
mods = {}  # Map from filename to list of mods.
for fn in glob('*.json'):
    mods[fn] = json.load(open(fn))
pbar = progressbar.ProgressBar(
    widgets=['', ' ', progressbar.Percentage(), progressbar.Bar(), progressbar.ETA()],
    maxval=sum(map(len, mods))).start()
# Get the newest (specified) version of each mod, write manifest:
data = {}
for fn, mods in mods.iteritems():
    pbar.widgets[0] = fn
    data[fn] = {}
    for name, d in GetNewestVersions(mods):
        data[fn][name] = d
    with open(fn + '-manifest', 'w') as manifest:
        json.dump(data[fn], manifest, indent=2)
# Update MODS.md.
with open('../MODS.md', 'w') as f:
  f.write(GenerateModList(data))
pbar.finish()

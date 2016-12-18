#!/usr/bin/env python
#
# This autogenerates .json-manifest files from the .json input file(s).
#
# Call this from the root of the git repository.

from concurrent.futures import ThreadPoolExecutor
from glob import glob
from HTMLParser import HTMLParser
from lxml.html import soupparser
from urllib import pathname2url
from urllib2 import urlopen
import hashlib
import json
import os
import re
import sys
import time
import threading
import urlparse

# No. of concurrent HTTP connections.
MAX_CONCURRENCY = 8
http_sem = threading.Semaphore(MAX_CONCURRENCY)
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY*2)
completed_mods = 0
total_mods = None

COMMENT = 'comment'
DEPENDENCIES = 'dependencies'
ENCODED = 'encoded'
FILENAME = 'filename'
HASH = 'md5'
LOCAL = 'local'
MISSING = 'missing'
PROJECTID = 'projectID'
PROJECTPAGE = 'projectPage'
REMOTE = 'remote'
SRC = 'src'
TITLE = 'title'
TYPE = 'type'
VERSION = 'version'


# This is a blatant security hole.
# But you won't run this on an untrusted computer, right?
# At least fix it first.
CACHEDIR = '/tmp/tppi3-manifest-updater'
if not os.path.exists(CACHEDIR):
    os.mkdir(CACHEDIR)

def VerboseErrors(f):
    def w(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            print 'Inside %s(%s)%s:' % (f.func_name, args, kwargs)
            raise
    return w


def FileCache(prefix):
    def Prefixed(f):
        def g(url):
            hopefully_unique = prefix + ' ' + re.sub('/', '_', url)
            cachefile = os.path.join(CACHEDIR, hopefully_unique)
            if os.path.exists(cachefile):
                if time.time() - os.path.getmtime(cachefile) > 3600:
                    os.remove(cachefile)
                else:
                    return open(cachefile).read()
            contents = f(url)
            open(cachefile, 'w').write(contents)
            return contents
        return g
    return Prefixed


@FileCache('Get')
def Get(url):
    if url.startswith('.'):
        # This is a local file, in git.
        return open(url).read()
    with http_sem:
        req = None
        try:
            req = urlopen(url)
            return req.read()
        finally:
            req and req.close()


@FileCache('Deref')
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
    pbar = [0, 0]
    pbar_lock = threading.Lock()

    def StartProgressbar(mods, state=''):
        print ''
        if state:
            print '#', state
        pbar[0] = 0
        pbar[1] = len(mods)

    def IncProgressbar(state=''):
        with pbar_lock:
            print  '%24.24s: %d / %d' % (state, pbar[0], pbar[1])
            pbar[0] += 1

    def FixupData(data):
        if data.get(SRC) is None:
            data[TYPE] = MISSING
        elif data[SRC].startswith('http'):
            data[TYPE] = REMOTE
        else:
            data[TYPE] = LOCAL
        if FILENAME in data:
            if not (data[FILENAME].endswith('.jar') or data[FILENAME].endswith('.zip')):
                data[FILENAME] += '.jar'
            if not VERSION in data:
                data[VERSION] = ParseVersion(data[FILENAME])
            data[ENCODED] = pathname2url(data[FILENAME])
        return data

    @VerboseErrors
    def ModData(name):
        mod = mods[name]
        if SRC in mod:
            # This is a non-Curse mod.
            data = GetNonCurseData(name, mod) or {}
        else:
            data = GetNewestCurseData(name, mod) or {}
        for k in mod:
            if k[0] != '_':
                data[k] = mod[k]
        return (name, data)

    def GetNonCurseData(name, mod):
        jar = Get(mod[SRC])
        IncProgressbar(name)
        data = dict(mod)
        data[HASH] = hashlib.new(HASH, jar).hexdigest()
        data[FILENAME] = mod[SRC].split('/')[-1]
        return FixupData(data)

    def GetNewestCurseData(name, unused_mod):
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
        stability = tree.xpath('//td[@class="project-file-release-type"]/div/@class')
        assert len(files) == len(names) == len(stability)
        files_filtered = []
        names_filtered = []
        for i in xrange(len(files)):
          if 'alpha' not in stability[i]:
            files_filtered.append(files[i])
            names_filtered.append(names[i])
        if files_filtered:
          files = files_filtered
          names = names_filtered
        data = {
            PROJECTID: projectID,
            PROJECTPAGE: projectUrl,
            TITLE: projectTitle,
        }
        if files:
          # Find the URL, MD5 and filename of that file.
          filePage = Get(baseUrl + files[0])
          tree = soupparser.fromstring(filePage)
          hash = tree.xpath('//span[@class="%s"]/text()' % HASH)
          url = tree.xpath('//a[@class="button fa-icon-download"]/@href')
          filename = tree.xpath('//*[text()="Filename"]/following-sibling::div/text()')
          data[FILENAME] = filename[0]
          data[HASH] = hash[0]
          data[SRC] = baseUrl + url[0]
          # Find the dependencies for this file.
          dependencies = [
              int(url.split('/')[-1]) for url in
              tree.xpath('//*[text()="Required Library"]/following-sibling::ul/li/a/@href')
          ]
          data[DEPENDENCIES] = dependencies
        IncProgressbar(data[TITLE])
        return FixupData(data)

    # Putting it all together:
    # TODO(Baughn): I can feel the maintenance debt already.
    all_mods = []
    all_ids = set()
    all_deps = set()
    StartProgressbar(mods)
    desired_mods = executor.map(ModData, sorted(mods))
    for name, mod in desired_mods:
        if PROJECTID in mod:
            # Only for Curse mods.
            all_ids.add(mod[PROJECTID])
        all_deps.update(mod.get(DEPENDENCIES, []))
        all_mods.append((name, mod))
    required_mods = lambda: all_deps.difference(all_ids)
    while required_mods():
        StartProgressbar(required_mods(), 'Dependencies:')
        dependency_mods = executor.map(
            lambda id: GetNewestCurseData(id, None),
            required_mods())
        for mod in dependency_mods:
            all_ids.add(mod[PROJECTID])
            all_deps.update(mod.get(DEPENDENCIES, []))
            all_mods.append((mod[PROJECTPAGE].split('/')[-1], mod))
    return all_mods


def GenerateModList(data):
    lines = ['# Mods']
    for filename in sorted(data):
        mods = data[filename]
        lines.append('## %s:' % filename)
        for name in sorted(mods):
            mod = mods[name]
            lines.append('- [%s](%s): %s' % (
                mod.get(TITLE) or name,
                mod.get(PROJECTPAGE) or urlparse.urljoin(mod.get(SRC), '/'),
                mod.get(VERSION)))
            if mod and COMMENT in mod:
                lines.append('')
                lines.append('  ' + mod[COMMENT])
            if not mod or not FILENAME in mod:
                lines.append('```diff')
                lines.append('- Not yet on 1.10 (probably)')
                lines.append('```')
        lines.append('')
    return '\n'.join(lines)


# Find manifests to construct:
mods = {}  # Map from filename to list of mods.
for fn in glob('manifest/*.json'):
    mods[fn] = json.load(open(fn))
# Get the newest (specified) version of each mod, write manifest:
data = {}
for fn, mods in mods.iteritems():
    data[fn] = {}
    for name, d in GetNewestVersions(mods):
        data[fn][name] = d
    with open(fn + '-manifest', 'w') as manifest:
        json.dump(data[fn], manifest, indent=2)
# Update MODS.md.
with open('MODS.md', 'w') as f:
  f.write(GenerateModList(data))

import httplib
import socket
import mechanize
import urllib2
from multiprocessing.pool import ThreadPool
from BeautifulSoup import BeautifulSoup as soup
from collections import defaultdict
from threading import Lock

BASE_DOMAIN = "http://www.appneta.com"
BASE_URL = "http://www.appneta.com/blog/"
RESULT_DIR = "./results"
TIMEOUT = 5

socket.setdefaulttimeout(TIMEOUT)

class LinkCheck(object):
    def __init__(self, base_url, result_dir='./results'):
        self.base_url = base_url

        self.checked = set()
        self.broken = defaultdict(list)

        self.pool = ThreadPool(5)
        self.results = []

        self.progress = 0
        self.report_interval = 500
        self.result_dir = result_dir

        self.mut = Lock()

    def check(self):
        self.crawl(self.base_url)

        while self.results:
            print len(self.results)
            r = self.results.pop()
            r.get()

    def crawl(self, url, prev='--root--', image=False):
        try:
            self.do_crawl(url, prev, image)
        except Exception, e:
            print "don't kill the thread pool bro: ", e
            return

    def do_crawl(self, url, prev='--root--', image=False):
        br = mechanize.Browser()
        br.set_handle_robots(False)

        self.mut.acquire()
        self.progress += 1
        print 'CHECKING ', url, " via ", prev, image, self.progress
        if self.progress % self.report_interval == 0:
            self.write_report()
        self.mut.release()

        url = url.encode('utf-8')

        if url in self.broken:
            self.broken[url].append(prev)

        if url in self.checked:
            return

        self.checked.add(url)
        try:
            html = br.open(url, timeout=TIMEOUT)
        except urllib2.HTTPError, e:
            # this usually means status code
            if e.code == 404 or e.code == 500:
                self.broken[url].append(prev)
                print 'Found broken: %s / %s' % (url, e.code)
                return
            elif e.code == 403:
                # lots of robot issues, ignore
                return
            else:
                print 'Unrecognized error %s: %s / %s' % (e.code, url, prev)
                return
        except urllib2.URLError, e:
            # this usually means timeout
            self.broken[url].append(prev)
            print 'Found broken: %s, %s' % (url, str(e))
            return
        except Exception, e:
            # catch-all
            self.broken[url].append(prev)
            print 'Found broken: %s, %s' % (url, str(e))
            return

        # no need to go farther if this is an image / download
        if image or not br.viewing_html():
            return

        # no need to go further if this is external
        if (not 'www.appneta.com' in url and not '/appneta.com' in url):
            return

        # recursive link traversal -- cache links first
        links = [l for l in br.links()]

        def fix_url(next_url):
            if next_url[0:4] == 'http':
                return next_url
            elif next_url[0] == '/':
                next_url = BASE_DOMAIN + next_url
            else:
                next_url = url.rsplit('/', 1)[0] + '/' + next_url
            return next_url

        # check that images load
        bs_parsed = soup(html)
        image_tags = bs_parsed.findAll('img')

        for i in image_tags:

            next_url = i['src']
            if next_url[0:4] != 'http':
                next_url = fix_url(next_url)
            self.results.append(self.pool.apply_async(self.crawl, (next_url, url, True)))

        # recursive link traversal
        for l in links:
            next_url = l.url
            if next_url[0] != '#' and next_url[0:6] != 'mailto' and next_url[0:10] != 'javascript' and next_url[0:1] != '.':
                next_url = fix_url(next_url)
                self.results.append(self.pool.apply_async(self.crawl, (next_url, url, False)))


    def report(self):
        # reverse our broken map...
        outbound = defaultdict(list)
        for (broken, refs) in self.broken.iteritems():
            for r in refs:
                outbound[r].append(broken)

        ret = ''
        for (src, dests) in outbound.iteritems():
            for d in dests:
                ret += "%s, %s\n" % (src, d,)

        return ret

    def write_report(self):
        f = open(self.result_dir + '/results_%d.csv' % (self.progress, ), 'w')
        rep = self.report()
        f.write(rep)
        print rep
        f.close()

l = LinkCheck(BASE_URL, RESULT_DIR)
l.check()
l.write_report()

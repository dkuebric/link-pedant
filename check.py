import httplib
import socket
import mechanize
import urllib2
from BeautifulSoup import BeautifulSoup as soup
from collections import defaultdict

BASE_DOMAIN = "http://www.appneta.com"
BASE_URL = "http://www.appneta.com/blog"

socket.setdefaulttimeout(3.0)

class LinkCheck(object):
    def __init__(self, base_url):
        self.base_url = base_url
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)

        self.checked = set()
        self.broken = defaultdict(list)

        self.progress = 0

    def check(self):
        self.crawl(self.base_url)

    def crawl(self, url, prev='--root--', image=False):

        self.progress += 1

        if self.progress % 100 == 0:
            self.report()

        url = url.encode('utf-8')

        if url in self.broken:
            self.broken[url].append(prev)

        if url in self.checked:
            return

        print 'CHECKING ', url, " via ", prev, image

        self.checked.add(url)
        try:
            html = self.br.open(url, timeout=3)
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
        if image or not self.br.viewing_html():
            return

        # no need to go further if this is external
        if not 'www.appneta.com' in url and not '/appneta.com' in url:
            return

        # recursive link traversal -- cache links first
        links = [l for l in self.br.links()]

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
            self.crawl(next_url, url, True)

        # recursive link traversal
        for l in links:
            next_url = l.url
            if next_url[0] != '#' and next_url[0:6] != 'mailto' and next_url[0:10] != 'javascript' and next_url[0:1] != '.':
                next_url = fix_url(next_url)
                self.crawl(next_url, url)


    def report(self):
        # reverse our broken map...
        outbound = defaultdict(list)
        for (broken, refs) in self.broken.iteritems():
            for r in refs:
                outbound[r].append(broken)

        for (src, dests) in outbound.iteritems():
            print src
            for d in dests:
                print "-- %s" % (d,)

l = LinkCheck(BASE_URL)
l.check()
l.report()

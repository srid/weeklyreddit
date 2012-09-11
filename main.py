import import_wrapper

import os
import datetime
import logging
import json

import webapp2 as webapp
from google.appengine.ext        import db
from google.appengine.ext.webapp import template
from google.appengine.api        import users
from google.appengine.api        import urlfetch

from PyRSS2Gen   import RSS2, RSSItem, Guid


SITE_URL = 'http://weeklyreddit.appspot.com'
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
USER_AGENT = 'weeklyreddit from github.com/srid/weeklyreddit; served by %s' % os.environ['SERVER_SOFTWARE']
logging.info('running with user agent: %s', USER_AGENT)


class RedditAPIError(Exception): 
    pass


def request_reddit(url):
    result = urlfetch.fetch(url, headers={'User-Agent': USER_AGENT})
    if result.status_code != 200:
        raise RedditAPIError('http response [%s] for %s - content: %s' % (result.status_code, url, result.content))
    j = json.loads(result.content)
    if 'error' in j:
        raise RedditAPIError(j['error'])
    return j


def render_template(path):
    """Render the given template with basic template vars containing user info"""
    return webapp.Response(template.render(os.path.join(TEMPLATES_DIR, path), {
        'is_admin':   users.is_current_user_admin(),
        'login_url':  users.create_login_url("/"),
        'logout_url': users.create_logout_url("/"),
        }))


class CurrentWeekEntry(db.Model):
    """Stores current week top links in JSON format.
    
    During next week, simply update the db.
    
    This model makes sure that we update RSS only once per week.
    """
    
    subreddit = db.StringProperty(required=True)
    top_links_json = db.TextProperty()
    datetime = db.DateTimeProperty(required=True)
    
    @staticmethod
    def reddit_top_links_for_this_week(subreddit):
        """Cached version of reddit_top_links() -- that runs once a week"""
        now = datetime.datetime.now()
        
        q = CurrentWeekEntry.all().filter("subreddit = ", subreddit)
        if q.count() == 0:
            entry = CurrentWeekEntry(subreddit=subreddit, datetime=now)
            force_update = True
        else:
            entry = q[0]
            force_update = False

        a_week = datetime.timedelta(days=7)
        if force_update or entry.datetime + a_week < now:
            logging.info("Updating top links for '%s'" % subreddit)
            j = reddit_top_links(subreddit)
            entry.top_links_json = json.dumps(j)
            entry.datetime = now
            entry.put()
        else:
            logging.debug("Reusing top links for '%s'" % subreddit)
            j = json.loads(entry.top_links_json)
        return j


def reddit_top_links(subreddit):
    """ Return top links in a given subreddit. If `subreddit` is None, use the
    main reddit. """
    # reddit provides a JSON api
    # see: http://code.reddit.com/ticket/154
    top_url = "http://www.reddit.com/r/%s/top/.json?t=week" % subreddit
    j = request_reddit(top_url)
    return j['data']['children']

    
def reddit_top_links_rss(subreddit):
    rss_items = []
    for link in CurrentWeekEntry.reddit_top_links_for_this_week(subreddit):
        link = link['data']
        comments_url = 'http://reddit.com/r/{subreddit}/comments/{id}'.format(**link)
        rss_items.append(
            RSSItem(
                title = "%s (%d points; %d comments)" % (
                    link['title'],
                    link['score'],
                    link['num_comments']),
                link = link['url'],
                author = link['author'],
                description = '<a href="%s">View comments on reddit</a>' % comments_url,
                guid = Guid(link['url']),
                pubDate = datetime.datetime.fromtimestamp(link['created'])
            )
        )
   
    return RSS2(
        title = 'r/%s - top reddit links' % subreddit,
        link = SITE_URL,
        description = 'read top links in reddit every week',
        items = rss_items
    ).to_xml()

 
def main_page(request):
    return render_template("main.html")


def rss_page(request, subreddit='reddit.com'):
    xml = reddit_top_links_rss(subreddit)
    return webapp.Response(xml, content_type='application/rss+xml')


application = webapp.WSGIApplication([
    webapp.Route('/', handler=main_page),
    webapp.Route('/rss/<subreddit:\w+>', handler=rss_page),
    webapp.Route('/rss', handler=rss_page),
    ],
    debug=True  # this will show a traceback to the user, which is ok for this app
)
import import_wrapper

import os
import datetime
import urllib
import logging
import json
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


from google.appengine.ext import webapp, db
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api        import users

from PyRSS2Gen   import RSS2, RSSItem, Guid


SITE_URL = 'http://weeklyreddit.appspot.com'

 
class SimpleRequestHandler(webapp.RequestHandler):
    
    def __init__(self, *args, **kwargs):
        super(SimpleRequestHandler, self).__init__(*args, **kwargs)
        self.view = {}
    
    def render_view(self, name):
        path = os.path.join(os.path.dirname(__file__),
                            'templates',
                            name)
        
        self.view.update({
            'is_admin':   users.is_current_user_admin(),
            'login_url':  users.create_login_url("/"),
            'logout_url': users.create_logout_url("/"),
        })
        
        self.response.out.write(template.render(path, self.view))
        

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
            logging.info("Reusing top links for '%s'" % subreddit)
            j = json.loads(entry.top_links_json)
        return j
        

def file_write_to_string(file_writer):
    """Call `file_writer' with a file-like object as argument and return
    the written contents of that file
    """
    sio = StringIO()
    
    try:
        file_writer(sio)
        text = sio.getvalue()
    finally:
        sio.close()
        
    return text

        
def reddit_top_links(subreddit):
    """ Return top links in a given subreddit. If `subreddit` is None, use the
    main reddit. """
    
    # reddit provides a JSON api
    # see: http://code.reddit.com/ticket/154
    top_url = "http://www.reddit.com/r/%s/top/.json?t=week" % subreddit
    
    j = json.load(urllib.urlopen(top_url))
    return j['data']['children']
    
def link_description(link_data):
    comments_link = "http://reddit.com/r/%s/comments/%s" % (link_data['subreddit'],
                                                            link_data['id'])
    return '<a href="%s">Comments Link</a>' % comments_link
    
def reddit_top_links_rss(subreddit):
    rss_items = []
    
    for link in CurrentWeekEntry.reddit_top_links_for_this_week(subreddit):
        link = link['data']
        comments_url = 'http://reddit.com/r/%s/comments/%s' % (link['subreddit'],
                                                               link['id'])
        rss_items.append(
            RSSItem(
                title = "%s (%d points; %d comments)" % (link['title'],
                                                         link['score'],
                                                         link['num_comments']),
                link = link['url'],
                author = link['author'],
                description = link_description(link),
                guid = Guid(link['url']),
                pubDate = datetime.datetime.fromtimestamp(link['created'])
            )
        )
   
    rss = RSS2(
        title = '%s - top reddit links' % subreddit,
        link = SITE_URL,
        description = 'read top links in reddit every week',
        items = rss_items
    )
    
    return file_write_to_string(rss.write_xml)

 
class MainPage(SimpleRequestHandler):
    
    def get(self):
        self.render_view("main.html")
        
        
class RSSPage(SimpleRequestHandler):
    
    def get(self, parent_re_group, subreddit):
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.out.write(
            reddit_top_links_rss(subreddit or 'reddit.com')
        )
        

application = webapp.WSGIApplication([
    ('/', MainPage),
    ('/rss(/([a-zA-Z_]+))?', RSSPage)
    ],
    debug=True
)

""" Old code:
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
"""
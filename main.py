import import_wrapper

import os
import datetime
import urllib
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api        import users

from PyRSS2Gen   import RSS2, RSSItem, Guid
import simplejson as json


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
    top_url = "http://www.reddit.com/r/%s/top/.json?t=week" % (subreddit or "reddit.com")
    
    j = json.load(urllib.urlopen(top_url))
    return j['data']['children']
    
def link_description(link_data):
    comments_link = "http://reddit.com/r/%s/comments/%s" % (link_data['subreddit'],
                                                            link_data['id'])
    return '<a href="%s">Comments Link</a>' % comments_link
    
def reddit_top_links_rss(subreddit):
    rss_items = []
    
    for link in reddit_top_links(subreddit):
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
            reddit_top_links_rss(subreddit)
        )
        

application = webapp.WSGIApplication([
    ('/', MainPage),
    ('/rss(/([a-z]+))?', RSSPage)
    ],
    debug=True
)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
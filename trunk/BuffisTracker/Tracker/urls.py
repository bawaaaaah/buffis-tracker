from django.conf.urls.defaults import *
from django.views.generic import list_detail
from BuffisTracker.Tracker.models import *
from BuffisTracker.Tracker.views import *

torrent_dict = {
        'queryset' : Torrent.objects.all(),
        'template_name' : 'torrent_detail.html',
        }

urlpatterns = patterns('',
    # Main page for torrents.
    (r'^$', main_page),

    # View related to displaying and downloading a torrent.
    (r'^torrent/(?P<object_id>\d+)/$', 'django.views.generic.list_detail.object_detail', torrent_dict),
    (r'^postcomment/(?P<torrent_id>\d+)/$', post_comment),
    (r'^download/(?P<object_id>\d+)/$', download_torrent),

    # Listings
    (r'^category/(?P<category>.+?)/$', torrents_for_category),
    (r'^tag/(?P<tag_name>.+?)/$', torrents_for_tag),
    (r'^user/(?P<username>.+?)/$', torrents_for_user),
    (r'^search/$', torrents_for_search),
    (r'^mytorrents/$', my_torrents),

    # View used for uploading new torrents.
    (r'^upload/$', upload_torrent),

    # Profile for torrent user.
    (r'^profile/$', profile),
    
    # Announce for tracker.
    (r'^announce/(?P<torrent_pass>[^/]+)/$', announce),
    (r'^announce/$', announce),
)

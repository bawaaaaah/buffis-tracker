from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Torrent urls.
    (r'^torrents/', include('BuffisTracker.Tracker.urls')),

    # Only for development!
    (r'^pics/(?P<path>.*)$', 'django.views.static.serve', {'document_root': '/Users/buffi/Documents/Code/Django/BuffisTracker/pics'}),

    # Admin.
    (r'^admin/', include(admin.site.urls)),
)

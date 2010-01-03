from django.db import models
from django.contrib.auth.models import User

def _get_readable_size(num_bytes):
    num_bytes = float(num_bytes)
    if num_bytes > 1073741824:
        return "%.2f GB" % (num_bytes / 1073741824)
    elif num_bytes > 1048576:
        return "%.2f MB" % (num_bytes / 1048576)
    elif num_bytes > 1024:
        return "%.2f kB" % (num_bytes / 1024)
    else:
        return "%d B" % num_bytes

class Category(models.Model):
    name = models.CharField(max_length=30)

    def get_absolute_url(self):
        return "/torrents/category/%s/" % self.name

    def __unicode__(self):
        return self.name

class Peer(models.Model):
    user = models.ForeignKey(User, blank=True, null=True)
    ip = models.IPAddressField()
    port = models.IntegerField()
    peer_id = models.CharField(max_length=40) # In hex.
    seen = models.DateTimeField(auto_now = True)
    seeding = models.BooleanField(default = False)
    downloaded = models.IntegerField(default = 0)
    uploaded = models.IntegerField(default = 0)

    def __unicode__(self):
        return self.peer_id

class Tag(models.Model):
    name = models.CharField(max_length=100)

    def get_absolute_url(self):
        return "/torrents/tag/%s/" % self.name

    def __unicode__(self):
        return self.name

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique = True)
    uploaded = models.IntegerField(default = 0)
    downloaded = models.IntegerField(default = 0)
    torrent_pass = models.CharField(max_length = 32)

    @property
    def num_torrents(self):
        return self.user.torrent_set.count()

    @property
    def downloaded_readable(self):
        return _get_readable_size(self.downloaded) 

    @property
    def uploaded_readable(self):
        return _get_readable_size(self.uploaded) 

    def __unicode__(self):
        return unicode(self.user)

class Torrent(models.Model):
    name = models.CharField(max_length=128) 
    filename = models.CharField(max_length=256)
    user = models.ForeignKey(User)
    timestamp = models.DateTimeField(auto_now_add=1)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, null=True)
    category = models.ForeignKey(Category)
    numFiles = models.IntegerField(default=1)
    filesize = models.IntegerField(default=1)
    
    info_hash = models.CharField(max_length=40) # In hex.
    peers = models.ManyToManyField(Peer, blank=True, null=True)
    seeders = models.IntegerField(default=0)
    leechers = models.IntegerField(default=0)
    downloads = models.IntegerField(default=0)

    @property
    def filesize_readable(self):
        return _get_readable_size(self.filesize)

    def get_absolute_url(self):
        return "/torrents/torrent/%d/" % self.id

    def get_download_url(self):
        return "/torrents/download/%d/" % self.id

    def __unicode__(self):
        return self.name

class Comment(models.Model):
    user = models.ForeignKey(User)
    torrent = models.ForeignKey(Torrent)
    text = models.TextField(blank=True) 
    timestamp = models.DateTimeField(auto_now_add=1)

    def __unicode__(self):
        return "Comment #%d" % self.id

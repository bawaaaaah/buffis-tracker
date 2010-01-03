from django.shortcuts import get_object_or_404, render_to_response
from socket import inet_aton
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.template import RequestContext
from django.forms import ModelForm
from django.views.generic import list_detail
from BuffisTracker.Tracker.models import *
from django import forms
import BuffisTracker.settings
import BuffisTracker.Tracker.lib.bencode as bencode
import os.path
import datetime

DEFAULT_ANNOUNCE_URL = 'http://127.0.0.1:8000/torrents/announce/'
DEFAULT_TORRENT_ROOT = '/tmp/'
DEFAULT_TORRENTS_PER_PAGE = 30
DEFAULT_TORRENT_INTERVAL = 30*60 # 30 minutes
DEFAULT_TORRENT_MAX_REPLY_PEERS = 50

class TorrentForm(forms.Form):
    name = forms.CharField(max_length=100)
    file = forms.FileField()
    description = forms.CharField(widget=forms.Textarea())
    category = forms.ModelChoiceField(queryset=Category.objects.all())
    tags = forms.CharField(max_length=100, help_text='Separate tags by whitespace.')

def make_new_torrent_pass():
    import random, string
    return "".join(random.sample(string.ascii_letters, 32))

def get_random_peers(queryset, num_random):
    import random
    peers = list(queryset.all())
    random.shuffle(peers)
    return peers[:num_random]

def make_main_context_data():
    return {'top_tags' : Tag.objects.all(), 'categories' : Category.objects.all()}

def download_torrent(request, object_id):
    """ 
    Request sent when user clicks a download link for a torrent. 
    The response will be a torrent with mime type application/x-bittorrent.
    On failure, a 404 is sent.
    """

    announce_url = getattr(BuffisTracker.settings, 'ANNOUNCE_URL', DEFAULT_ANNOUNCE_URL)

    torrent = get_object_or_404(Torrent, id=object_id)
    filename = torrent.filename

    torrent_root = getattr(BuffisTracker.settings, 'TORRENT_ROOT', DEFAULT_TORRENT_ROOT)
    local_filename = os.path.join(torrent_root, filename)
    local_file = open(local_filename, 'rb')

    response = HttpResponse(mimetype="application/x-bittorrent")
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    if request.user.is_authenticated():
        data = bencode.bdecode(local_file.read())
        user_profile, created = UserProfile.objects.get_or_create(user=request.user, defaults={'torrent_pass' : make_new_torrent_pass()})
        data["announce"] = str("%s%s/" % (announce_url, user_profile.torrent_pass))
        if "announce-list" in data:
            del data["announce-list"]
        response.write(bencode.bencode(data))
    else:
        data = bencode.bdecode(local_file.read())
        data["announce"] = str(announce_url)
        if "announce-list" in data:
            del data["announce-list"]
        response.write(bencode.bencode(data))
    return response

@login_required
def profile(request):
    """
    Displays the torrent profile of the user (seeded/leeched data and number of uploaded torrents).
    """

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'torrent_pass' : make_new_torrent_pass()})
    extra_context = make_main_context_data()
    extra_context.update({'user' : request.user, 'profile' : user_profile})
    return render_to_response('torrent_profile.html',
            extra_context,
            context_instance=RequestContext(request))

@login_required
def post_comment(request, torrent_id):
    """
    Posts a new comment to a torrent. Will redirect to torrent afterwards.
    """

    torrent = get_object_or_404(Torrent, id=torrent_id)
    if request.method == 'POST': # If the form has been submitted...
        new_comment = request.POST.get('NewComment', '')
        if new_comment:
            Comment(user=request.user, text=new_comment, torrent=torrent).save()

    return HttpResponseRedirect(torrent.get_absolute_url())

@login_required
def upload_torrent(request):
    """
    Page for torrent uploading.
    When first visiting this page (through a regular GET request), the user will be presented with a form.

    When the form is submitted, it is validated and then processed.
    For the torrent file submitted the following is modified before it is saved:
        1. Announce URL is set to this pages announce url (ANNOUNCE_URL in settings.py).
        2. The announce-list tag is cleared. This removes other announcers.
    The torrent will then be saved to TORRENT_ROOT from settings.py.

    A new Torrent object is created for this .torrent file. The user is redirected there afterwards.
    """

    announce_url = getattr(BuffisTracker.settings, 'ANNOUNCE_URL', DEFAULT_ANNOUNCE_URL)

    if request.method == 'POST': # Called on form submission.
        form = TorrentForm(request.POST, request.FILES) # Get bound form.
        if form.is_valid(): 
            clean = form.cleaned_data

            data = bencode.bdecode(form.cleaned_data['file'].read())
            data['announce'] = announce_url
            if 'announce-list' in data:
                del data['announce-list']

            if "files" in data['info']: # multifile
                filesize = sum([f["length"] for f in data['info']['files']])
                numfiles = len(data['info']['files'])
            else:
                filesize = data['info']['length']
                numfiles = 1
            encoded_data = bencode.bencode(data)
            info_hash = bencode.get_hash(encoded_data).encode("hex")

            # Write torrent to disk
            torrent_root = getattr(BuffisTracker.settings, 'TORRENT_ROOT', DEFAULT_TORRENT_ROOT)
            local_filename = os.path.join(torrent_root, clean['file'].name)
            local_file = open(local_filename, 'wb+')
            local_file.write(encoded_data)
            local_file.close()

            # Create torrent in database.
            new_torrent = Torrent(
                    name=clean['name'], 
                    description=clean['description'], 
                    category=clean['category'], 
                    user=request.user,
                    filename=clean['file'].name,
                    numFiles=numfiles,
                    info_hash=info_hash,
                    filesize=filesize)
            new_torrent.save()

            # Handle tags.
            tags = clean['tags'].split()
            for tag in tags:
                tag_object, created = Tag.objects.get_or_create(name=tag)
                new_torrent.tags.add(tag_object)

            return HttpResponseRedirect(new_torrent.get_absolute_url()) # Redirect after POST
    else:
        form = TorrentForm() # An unbound form

    return render_to_response('torrent_upload.html',
            {'form' : form, 'announce_url': announce_url},
            context_instance=RequestContext(request))

def show_torrent_list(request, queryset, list_header):
    """
    Displays a listing of torrents. This is used on the mainpage, for tags/categories/users/search or basically 
    anywhere where torrents should be listed.

    The user can order the torrents by setting the GET attribute order_by.
    The user can select the page by setting the GET attribute page.
    Example: /?page=3&order_by=-name

    The listing will contain the following template variables in addition to the ones available on all pages.
        torrent_list : The torrents to list.
        order_by : The field to order them by.
        list_header : Header for the listing.
        paginator : A Paginator object for the listing.
        page_obj : A Page object for the current page being listed.
    """
    
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    # Order the listed items through the GET attribute 'order_by'.
    order_by = request.GET.get('order_by', 'name')
    allowed_orderings = ('name', '-name', 'seeders', '-seeders', 'leechers', '-leechers', 'filesize', '-filesize')
    if order_by not in allowed_orderings:
        order_by = 'name'
    queryset = queryset.order_by(order_by)

    extra_context = make_main_context_data()
    extra_context['order_by'] = order_by
    extra_context['list_header'] = list_header

    return list_detail.object_list(
        request,
        paginate_by = getattr(BuffisTracker.settings, 'TORRENTS_PER_PAGE', DEFAULT_TORRENTS_PER_PAGE),
        page = page,
        queryset = queryset,
        template_name = 'torrent_mainpage.html',
        template_object_name = 'torrent',
        extra_context = extra_context
    )

def main_page(request):
    """
    Displays the main page.
    """

    return show_torrent_list(request, Torrent.objects.all(), "Listing all torrents")

def torrents_for_category(request, category):
    """
    Displays all torrents for a category.
    """

    return show_torrent_list(request, Torrent.objects.filter(category__name=category), "Listing torrents in category %s" % category)

@login_required
def my_torrents(request):
    """
    Displays all torrents from the logged in user.
    """

    return torrents_for_user(request, request.user.username)

def torrents_for_user(request, username):
    """
    Displays all torrents for an user.
    """

    user = get_object_or_404(User, username=username)
    return show_torrent_list(request, Torrent.objects.filter(user__username=username), "Listing torrents from user %s" % username)

def torrents_for_search(request):
    """
    Displays all torrents for a search term.

    IMPORTANT: This is currently really horribly implemented. It should be optimized to handle large data sets.
    The current implementation just goes through all torrent names and check if they contain the searchterm (case-insensitive).
    """

    if request.method == 'POST': 
        try:
            searchterm = request.POST.get('searchterm', '')
        except ValueError:
            return HttpResponseRedirect('/torrents/')
    else:
        return HttpResponseRedirect('/torrents/')

    return show_torrent_list(request, Torrent.objects.filter(name__icontains=searchterm), "Listing torrents matching %s" % searchterm)

def torrents_for_tag(request, tag_name):
    """
    Displays all torrents for a tag.
    """

    tag = get_object_or_404(Tag, name=tag_name)
    return show_torrent_list(request, tag.torrent_set.all(), "Showing torrents with tag %s" % tag_name)

def announce(request, torrent_pass=None):
    """ 
    The announcer for the tracker.
    Requests to this is sent from torrent clients.
    """

    import cgi

    def get_indata_error(data):
        error = None
        if not "info_hash" in get_data:
            error = "no info hash"
        elif not "peer_id" in get_data:
            error = "no peer id"
        elif not "port" in get_data:
            error = "no port"
        elif not "uploaded" in get_data:
            error = "no uploaded"
        elif not "downloaded" in get_data:
            error = "no downloaded"
        elif not "left" in get_data:
            error = "no left"
        return error

    def make_error_response(error_msg):
        response = bencode.bencode({"failure reason": error_msg}) 
        return HttpResponse(response, mimetype="text/plain")

    # Make sure that the torrent client sent a query string.
    if request.META['QUERY_STRING']:
        get_data = cgi.parse_qs(request.META['QUERY_STRING'])
    else:
        return make_error_response("No query string")

    # Validate the torrents indata.
    error = get_indata_error(get_data)
    if error:
        return make_error_response(error)

    # Get users IP address.
    ip = request.META['REMOTE_ADDR'] 

    # Get the info hash of the torrent.
    info_hash = get_data["info_hash"][0].encode("hex")

    # Check if torrent exists.
    try:
        torrent = Torrent.objects.get(info_hash=info_hash)
    except Torrent.DoesNotExist:
        return make_error_response("No such torrent.")

    # Check if a peer exists, otherwise create a new one.
    peer_id = get_data["peer_id"][0].encode("hex")
    peer, created = torrent.peers.get_or_create(peer_id = peer_id, defaults = {'ip' : ip, 'port' : int(get_data["port"][0])})

    # True if the peer should be added to the peer list.
    add_peer = True 

    # Make peer into a seeder if he has all data.
    if int(get_data["left"][0]) == 0:
        peer.seeding = True
        peer.save()

    # Check if not just a regular call
    if "event" in get_data:
        event = get_data["event"][0]
        if event == "started":
            # reset uploaded / downloaded
            peer.downloaded = 0
            peer.uploaded = 0
            peer.save()
        elif event == "completed":
            torrent.downloads += 1
            torrent.save()
        elif event == "stopped":
            peer.delete()
            add_peer = False

    # Check if it is a registered user. Registered users are nice.
    if torrent_pass:
        try:
            profile = UserProfile.objects.get(torrent_pass = torrent_pass)
            profile.downloaded += int(get_data["downloaded"][0]) - peer.downloaded
            profile.uploaded += int(get_data["uploaded"][0]) - peer.uploaded
            profile.save()

            peer.uploaded = get_data["uploaded"][0]
            peer.downloaded = get_data["downloaded"][0]
            peer.user = profile.user # Bind user to peer.
            peer.save()
        except UserProfile.DoesNotExist:
            pass # Not a registered used, keep going.

    # Remove peers that haven't been seen in TORRENT_INTERVAL*2 minutes.
    torrent_interval = getattr(BuffisTracker.settings, 'TORRENT_INTERVAL', DEFAULT_TORRENT_INTERVAL)
    torrent.peers.filter(seen__lt = datetime.datetime.now()-datetime.timedelta(seconds=torrent_interval*2)).delete()

    # Add peer to peer list as long as he hasn't stopped.
    if add_peer:
        torrent.peers.add(peer)

    # Update values for leechers and seeders.
    torrent.leechers = torrent.peers.filter(seeding = False).count()
    torrent.seeders = torrent.peers.filter(seeding = True).count()
    torrent.save()

    # Check if the client wants a specific number of peers, otherwise default to TORRENT_MAX_REPLY_PEERS.
    if "numwant" in get_data and get_data["numwant"][0]: 
        max_peers = int(get_data["numwant"][0])
    else:
        max_peers = getattr(BuffisTracker.settings, 'TORRENT_MAX_REPLY_PEERS', DEFAULT_TORRENT_MAX_REPLY_PEERS)

    # Get a set of peers (randomized order) to return. Not using order_by='?' since it doesn't work with MySQL for
    # large data sets,
    peer_set = get_random_peers(torrent.peers, max_peers)

    if "compact" in get_data and get_data["compact"][0]: # Compact response.
        peers = "".join([inet_aton(str(p.ip)) + chr(p.port>>8) + chr(p.port&255) for p in peer_set]) 
    else: # Normal response.
        if "no_peer_id" in get_data and get_data["no_peer_id"][0]: # No peer_id in response.
            peers = [{"ip": str(p.ip), "port": int(p.port)} for p in peer_set]
        else: # Response with peer_id.
            peers = [{"peer id": str(p.peer_id), "ip": str(p.ip), "port": int(p.port)} for p in peer_set]

    # Bencode and send the response. 
    response = bencode.bencode({"interval": torrent_interval, "complete": torrent.seeders, "incomplete": torrent.leechers, "peers": peers}) 
    return HttpResponse(response, mimetype="text/plain")


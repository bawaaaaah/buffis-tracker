A simple bittorrent tracker written in Django.

It has a quite small set of features, and it isn't (currently) meant to replace the use of tbsource and similar engines.

It is instead focused on simplicity and it should be easy to integrate into existing Django applications. It should also be a good starting point for constructing more advanced trackers.

A demo is available at http://tracker.buffis.com .

**TODO:**
Search is currently implemented by filtering names that icontains the search term. This is quite expensive for large data sets. If you realize that it's too slow for you (with large data sets), consider disabling it.

I'll optimize it later.
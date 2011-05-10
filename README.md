epguides.py - epguides.com parser
=================================
[epguides.com](http://epguides.com) provides the HTML for the show episodes, what date they were released, the season, the episode number, and the full name for said episode. This script downloads the HTML files, then parses them and puts them in a cache file on the hard drive, from there using some regexp magic given an filename like `The.Walking.Dead.S01E05.Wildfire.HDTV.XviD-FQM.\[VTV\].avi` will return:

    1 05 Wildfire

which is the season number, followed by the episode number (zero padded) and the episode name.

Command line functions:
=======================

    $ epguides.py -h
    Usage: epguides.py [options] [[-n showname -s season # -e episode #] | [filename]]

    Options:
      -h, --help            show this help message and exit
      -n NAME               Show name
      -s SEASON             Season number
      -e EPISODE            Episode number
      -v, --verbose         Increase verbosity

      Managing Shows:
        This deals with the shows that are cached locally

        -l, --list-shows    List the shows currently cached locally
        -a SHOWNAME, --add-show=SHOWNAME
                            Add a show to subscribe to and cache data
        -d DSHOWNAME, --del-show=DSHOWNAME
                            Remove a show from the subscribed list
        --show-url=SHOWURL  URL at epguides, only required if automatic URL
                            creation fails

      Cache Options:
        These options deal with the cache required for the script, like
        rebuilding it, or removing it when it is no longer required.

        --del-cache         Delete the cache currently stored for shows
        --build-cache       Builds cache for shows that were added
        --refresh           Refresh cached data (complete clean, uses lot of
                            network bandwidth and requests to epguides)

Getting Started:
===============

First add a show, this is required for any and all shows you want to use this tool with. This is done so that we don't hit epguides.com's servers each time, and to create a subscribed list that is updated using --refresh.

    epguides.py -a "NCIS"

Then have it build the cache (downloads the raw data from the web, then parses it), this step is required since an internal cache has to be built for the tool to do the rest of its magic. The script currently bombs out if you don't do this and look up a show/season/episode

    epguides.py --build-cache

After building the cache you can view the information it holds using the -n, -s, -e options:

    $ epguides.py -n "NCIS"
    $ epguides.py -n "NCIS" -s 1
    $ epguides.py -n "NCIS" -s 1 -e 2
    1 02 Hung Out to Dry

However lets say you have a filename like "NCIS.S07E04.Good.Cop.Bad.Cop.HDTV.XviD-FQM.avi" it can automatically parse it and retrieve the data in a formatted fashion:

    $ epguides.py NCIS.S07E04.Good.Cop.Bad.Cop.HDTV.XviD-FQM.avi
    7 04 Good Cop, Bad Cop
    $ epguides.py "NCIS 718 - LOL.avi"
    7 18 Jurisdiction

There are several file formats supported, the main ones are:

    <showname>.S<season>E<episode> *
    <showname> <season><episode (we assume that there are no more than 99 episodes per season> *
    <showname> - <season>x<episode> *
    <showname> <season>x<episode> *
    <showname>.<year (ignored, for now)>S<season>E<episode> *

They are regular expressions located at line 532 in the list `filere`.

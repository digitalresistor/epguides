#!/usr/bin/env python

###
 # Copyright (c) 2010 Bert JW Regeer <bertjw@regeer.org>;
 #
 # Permission to use, copy, modify, and distribute this software for any
 # purpose with or without fee is hereby granted, provided that the above
 # copyright notice and this permission notice appear in all copies.
 #
 # THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 # WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 # MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 # ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 # WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 # ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 # OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 #
###

from HTMLParser import HTMLParser
import os
import urllib2 as urllib
import httplib
import re
import time
import logging
import sys
import time
import datetime

SETTINGS = {
	# This is the directory where we are going to store the settings, and various other things
	"settings_dir": "~/.episodes",
	
	# Change this to a location you want the cache, leave it as a non-absolute path and it will be placed under .episodes
	"cache_dir": "cache",
	
	# Epguides URL (with or without trailing slash)
	"epguides_url": "http://epguides.com",
}

LOGLEVEL = {
	0:	logging.ERROR,
	1:	logging.INFO,
	2:	logging.DEBUG,
}

class _epguides_parser(HTMLParser):
	"""Parse an epguide page for the show"""
	def __init__(self, *args, **kw):
		HTMLParser.__init__(self)
		self.foundpre = 0
		self.found = ""
		self.charset = "utf-8"

	def set_charset(self, charset):
		self.charset = charset

	def _content_type(self, content):
		self.charset = re.match(".*charset=(.*)$", content).group(1)
		logging.debug("epguide_parser: Setting content-type: %s" % self.charset)

	def handle_starttag(self, tag, attrs):
		if tag == "pre":
			self.foundpre = 1
		
		if tag == "meta":
			settype = False
			content = ""
			for (attrname, attrval) in attrs:
				if attrname.strip().lower() == "content":
					content = attrval
				if attrname.strip().lower() == "http-equiv":
					if attrval.strip().lower() == "content-type":
						settype = True
			
			if settype:
				self._content_type(content)

	def handle_endtag(self, tag):
		if tag == "pre":
			self.foundpre = 0

	def handle_data(self, data):
		if self.foundpre:
			#data = data.decode("iso-8859-1")
			data = data.decode(self.charset)
			self.found = u"%s%s" % (self.found, data)
			
	def parsed_found(self):
		return self.found

class HeadRequest(urllib.Request):
	def get_method(self):
		return "HEAD"

class URLException(Exception):
	pass

class Show(object):	
	# Sample string:
	# # on list    Season-  Episode number   Production number      Air date     Episode name
	# 151          7     -  13               713                    26/Jan/10    Jet Lag

	ereg = r"""
		^				# Start of the string
		(?:[\s]*?[\d]*\.?)		# Episode number on list
		[\s]{2,}			# Ignore whitespace
		(?P<season>[\d]*)		# Season number
		-				# Separator
		[\s]*				# Optional whitespace
		(?P<episode>[\d]*)		# Episode number
		[\s]{2,}			# Ignore whitespace
		(?P<product>.+|)		# Product number, or nothing
		[\s]{2,}			# Ignore whitespace
		(?P<airdate>[\w\s/]*?)		# Air-date
		[\s]{2,}			# Ignore whitespace
		(?P<name>.*)			# Episode name
		$				# End of line
		"""
	epre = re.compile(ereg, re.X | re.I)
	
	def __init__(self, settings, showname, showurl=None):
		self.showname = showname
		self.showurl = ""
		self.cfile = ""
		self.crfile = ""
		self.settings = settings
		self.raw = ""
		self.eps = {}
		
		if showurl is None:
			showurl = self.showname.lower()
			showurl = re.sub('^the[\s]', '', showurl)
			showurl = re.sub('[^_\w]', '', showurl)
			if not settings['epguides_url'].endswith("/"):
				settings['epguides_url'] = "%s/" % (settings['epguides_url'])
			self.showurl = "%s%s" % (settings['epguides_url'], showurl)
		else:
			self.showurl = showurl
		
		self.cfile = "%s/%s" % (self.settings['cache_dir'], re.sub('[^_\w]', '', self.showname))
		self.crfile = "%s%s" % (self.cfile, ".raw")
		
		logging.debug("Show- name: %s; URL: %s" % (self.showname, self.showurl))
	
	def check_url(self):
		try:
			check = urllib.urlopen(HeadRequest(self.showurl))
		except urllib.HTTPError:
			raise URLException("URL is not valid for show")
		
	def del_cache(self):
		logging.info("Removing cache: %s" % (self.showname))
		try:
			os.remove(self.cfile)
			os.remove(self.crfile)
		except:
			pass
	
	def build_cache(self):
		logging.info("Building cache: %s" % (self.showname))
		self._cache_internal()
		
	def list_data(self, season=None, episode=None):
		self._parse_internal()
		
		if season is None:
			for (season, episodes) in self.eps.iteritems():
				for (number, data) in episodes.iteritems():
					print "%d %02d %s" % (season, number, data['name'])
		else:
			if episode is None:
				if season in self.eps:
					for (number, data) in self.eps[season].iteritems():
						print "%d %02d %s" % (season, number, data['name'])
				else:
					print >> sys.stderr, "Season doesn't exist"
					raise RuntimeError("Season doesn't exist")
			else:
				if season in self.eps:
					if episode in self.eps[season]:
						print "%d %02d %s" % (season, episode, self.eps[season][episode]['name'])
					else:
						print >> sys.stderr, "Episode doesn't exist"
						raise RuntimeError("Episode doesn't exist")
				else:
					print >> sys.stderr, "Season doesn't exist"
					raise RuntimeError("Season doesn't exist")
	
	
	def _update_raw_cache(self):
		try:
			logging.debug("Show- name: %s; cache update (raw)" % (self.showname))
			c = open(self.crfile, mode='w+')
			show = urllib.urlopen(self.showurl)
			if show.getcode() is not 200:
				logging.error("Failed to retrieve data for show: %s at %s" % (self.showname, self.showurl))
				raise RuntimeError("Failed to retrieve data for show")
			ep = _epguides_parser()
			ep.feed(show.read())
			show.close()
		
			raw = ep.parsed_found();
		
			c.write(raw.encode('UTF-8'))
			c.seek(0)
			
			return c
		except:
			c.close()
			os.remove(self.crfile)
			raise
	
	def _cache_raw(self):			
		if os.path.exists(self.crfile):
			mtime = os.path.getmtime(self.crfile)
			ctime = time.time() - 86400
			
			if mtime > ctime:
				logging.debug("Show- name: %s; cache new enough (raw)" % (self.showname))
				c = open(self.crfile, mode='r')
				self.raw = c
			else:
				self.raw = self._update_raw_cache()
		else:
			self.raw = self._update_raw_cache()
	
	def _parse_raw(self):
		self._cache_raw()
		
		logging.debug("Show- name: %s; cache parse (raw)" % (self.showname))
		
		for line in self.raw:
			line = line.strip()
			epm = Show.epre.match(line)
			if epm is not None:
				airdate = epm.group("airdate").replace('/', ' ')
				date = re.match("(?P<day>[\d]{1,2})?[\s]?(?P<month>[\w]{3,}?)[\s](?P<year>[\d]{2,4}?)$", airdate)
				
				airdate = ""
				if date is not None:
					adate = 0
					
					if date.group("year") is not None:
						if date.group("month") is not None:
							if date.group("day") is not None:
								try:
									adate = time.strptime("%s %s %s" % (date.group("day"), date.group("month"), date.group("year")), "%d %b %y")
									airdate = datetime.date(int(time.strftime("%Y", adate)), int(time.strftime("%m", adate)), int(time.strftime("%d", adate)))
									airdate = airdate.isoformat()
								except ValueError:
									logging.error("Invalid date encountered. Date ignored.")
									logging.debug("Day: %s Month: %s Year: %s" % (date.group("day"), date.group("month"), date.group("year")))

				if airdate == "":
					airdate = "0000-00-00"
						
				season = self.eps.setdefault(int(epm.group("season")), {})
				season[int(epm.group("episode"))] = {"name": epm.group("name").decode("UTF-8"), "airdate": airdate}
					
	
	def _parse_internal(self):
		self.eps = {}
		season = {}
		
		if self.eps != {}:
			return
		
		c = open(self.cfile, mode='r')
			
		for line in c:
			line = line.strip()
			
			if len(line) == 0:
				break
			
			lspl = line.split('\t')
			
			if len(lspl) == 2:
				season = self.eps.setdefault(int(lspl[1]), {})
			
			if len(lspl) == 3:
				season[int(lspl[0])] = {"name": lspl[2].decode("UTF-8"), "airdate": lspl[1]}
		
		c.close()
		
			
	def _cache_internal(self):
		if os.path.exists(self.cfile):
			mtime = os.path.getmtime(self.cfile)
			ctime = time.time() - 86100
			
			if mtime > ctime:
				logging.debug("Cache new enough: %s" % (self.showname))
				self._parse_internal()
				return
			else:
				self._parse_raw()
		else:
			self._parse_raw()
		
		try:
			c = open(self.cfile, mode='w')
		
			for season in self.eps.keys():
				c.write("Season\t%d\n" % (season))
				for episode in self.eps[season].iteritems():
					c.write("%d\t%s\t%s\n" % (episode[0], episode[1]['airdate'], episode[1]['name'].encode("UTF-8")))
		
			c.close()
		except:
			c.close()
			os.remove(self.cfile)
			raise

class Shows(object):
	"""Read the config file that contains the shows, and cache them"""
	def __init__(self, settings):
		# Set our internal settings
		self.settings = settings
		
		# Empty dictionary of shows
		self.shows = {}
		
		# Create the settings directory and fix up the paths
		self._create_settings_dir()
		
		# This is where we store what shows we are subscribed to
		self.subscribed = "%s/%s" % (self.settings['settings_dir'], "subscribed")
		
		# Load the shows, and cache them in memory
		self._load_settings()
	
	def _create_settings_dir(self):
		self.settings['settings_dir'] = os.path.expanduser(self.settings['settings_dir'])
		if not os.path.exists(self.settings['settings_dir']):
			logging.info("Settings directory created")
			os.mkdir(self.settings['settings_dir'])

		self.settings['cache_dir'] = os.path.expanduser(self.settings['cache_dir'])
		if not os.path.isabs(self.settings['cache_dir']):
			self.settings['cache_dir'] = "%s/%s" % (self.settings['settings_dir'], self.settings['cache_dir'])
			if not os.path.exists(self.settings['cache_dir']):
				logging.info("Cache directory created")
				os.mkdir(self.settings['cache_dir'])
	
	def _load_settings(self):
		if os.path.exists(self.subscribed):
			logging.debug("Loading subscribed shows.")
			c = open(self.subscribed, "r")
			
			for line in c:
				line = line.strip()
				if len(line) == 0:
					continue
				
				parts = line.split("\t")
				
				showname = parts[0].lower()
				showurl = None
				if len(parts) == 2:
					showurl = parts[1].lower()
				
				logging.debug("Loading: %s" % (showname))
				self.shows[showname] = Show(self.settings, showname, showurl=showurl)
			
			c.close()
		else:
			logging.debug("No subscribed list found.")
	
	def del_cache(self):
		for show in self.shows.itervalues():
			show.del_cache()
	
	def build_cache(self):
		for show in self.shows.itervalues():
			show.build_cache()
	
	def add_show(self, showname, showurl=None):
		showname = showname.lower()
		if showname in self.shows:
			print "Show already exists."
			return
		show = Show(self.settings, showname, showurl=showurl)
		show.check_url()
		
		c = open(self.subscribed, "a")
		if showurl is not None:
			c.write("%s\t%s\n" % (showname, showurl))
		else:
			c.write("%s\n" % showname)
		
		c.close()
	
	def del_show(self, showname):
		showname = showname.lower()
		if showname not in self.shows:
			print "Show doesn't exist"
			return
		
		self.shows.pop(showname).del_cache()
		
		try:
			c = open(self.subscribed, "r")
			d = open("%s.tmp" % self.subscribed, "w")
		
			for line in c:
				if line.strip().lower() == showname:
					continue
				else:
					d.write(line)
		
			c.close()
			d.close()
		
			os.rename("%s.tmp" % self.subscribed, self.subscribed)
		except:
			c.close()
			d.close()
			os.remove("%s.tmp" % self.subscribed)
			raise RuntimeError("Something failed, try again")
	
	def find_show(self, showname):
		showname = showname.lower().strip()
		
		if showname in self.shows:
			return self.shows[showname]
		else:
			return None 
		
	
	def list_cache(self):
		for name in sorted(self.shows.keys()):
			print name.title()

if __name__ == '__main__':
	from optparse import OptionParser
	from optparse import OptionGroup
	
	usage = "usage: %prog [options] [[-n showname -s season # -e episode #] | [filename]]"
	parser = OptionParser(usage=usage)
	
	parser.add_option("-n", dest="name", help="Show name")
	parser.add_option("-s", dest="season", type="int", help="Season number")
	parser.add_option("-e", dest="episode", type="int", help="Episode number")
	parser.add_option("-v", "--verbose", action="count", dest="verbose", default=0, help="Increase verbosity")
	
	group = OptionGroup(parser, "Managing Shows", "This deals with the shows that are cached locally")
	group.add_option("-l", "--list-shows", action="store_true", dest="listshows", help="List the shows currently cached locally")
	group.add_option("-a", "--add-show", action="store", dest="showname", help="Add a show to subscribe to and cache data")
	group.add_option("-d", "--del-show", action="store", dest="dshowname", help="Remove a show from the subscribed list")
	group.add_option("--show-url", action="store", dest="showurl", help="URL at epguides, only required if automatic URL creation fails")
	parser.add_option_group(group)
	
	group = OptionGroup(parser, "Cache Options", "These options deal with the cache required for the script, like rebuilding it, or removing it when it is no longer required.")
	group.add_option("--del-cache", action="store_true", dest="delcache", help="Delete the cache currently stored for shows")
	group.add_option("--build-cache", action="store_true", dest="buildcache", help="Builds cache for shows that were added")
	group.add_option("--refresh", action="store_true", dest="refresh", help="Refresh cached data (complete clean, uses lot of network bandwidth and requests to epguides)")
	parser.add_option_group(group)
	
		
	try:
		(options, args) = parser.parse_args()
		
		if options.verbose > 2:
			options.verbose = 2
		logging.basicConfig(level=LOGLEVEL[options.verbose])
		
		shows = Shows(SETTINGS)
		
		if options.name is not None and len(args) == 0:
			show = shows.find_show(options.name)
			
			if show is None:
				print >> sys.stderr, "Show not found"
				exit(1)
			
			show.list_data(season=options.season, episode=options.episode)
			exit(0)
			
		if options.delcache:
			print "Removing cache"
			shows.del_cache()
			exit(0)
		
		if options.buildcache:
			print "Building cache"
			shows.build_cache()
			print "Done building cache"
			exit(0)
		
		if options.refresh:
			print "Refreshing catalog"
			shows.del_cache()
			shows.build_cache()
			print "Done rebuilding catalog"
			exit(0)
		
		if options.showname is not None:
			print "Adding show: %s" % options.showname
			
			try:
				if options.showurl is not None:
					shows.add_show(options.showname, showurl=options.showurl)
				else:
					shows.add_show(options.showname)
			except URLException:
				logging.error("Automatic URL retrieval failed for show %s. Use --show-url." % (options.showname))
			exit(0)
		
		if options.dshowname is not None:
			print "Removing show: %s" % options.dshowname
			
			shows.del_show(options.dshowname)
		
		if options.listshows:
			print "Cached shows:"
			shows.list_cache()
			exit(0)
		
		if len(args) == 0:
			print >> sys.stderr, "Filename is required"
			raise RuntimeError("Filename is required")
		
		if len(args) > 1:
			print >> sys.stderr, "Too many arguments!"
			raise RuntimeError("Too many arguments!")
			
		filename = args[0]
		
		filere = [
			re.compile("(?:[./]*)(?P<showname>[\w.]+)\.(?:[\d]{4})\.S(?P<season>[\d]+)E(?P<episode>[\d]+)", re.I | re.X),
			re.compile("(?:[./]*)(?P<showname>[\w.]+)\.S(?P<season>[\d]+)\.?E(?P<episode>[\d]+)", re.I | re.X),
			re.compile("(?:[./]*)(?P<showname>[\w. ]+)[\s]+-[\s]+(?P<season>[\d]+)(?P<episode>[\d]{2}).*", re.I | re.X),
			re.compile("(?:[./]*)(?P<showname>[\w. ]+)[\s]+(?P<season>[\d]+)x?(?P<episode>[\d]{2}).*", re.I | re.X),
		]
		
		matchfound = False
		showname = ""
		season = 0
		episode = 0
		
		for rfile in filere:
			parts = rfile.match(filename)
			
			if parts is None:
				continue
				
			parts = parts.groupdict()
			
			showname = parts['showname'].replace('.', ' ').strip()
			season = int(parts['season'])
			episode = int(parts['episode'])
			matchfound = True
			break
		
		if not matchfound:
			print args
			print >> sys.stderr, "Unfortunately none of the filenames could be decoded."
			raise RuntimeError()
		
		
		show = shows.find_show(showname)
		
		if show is None:
			print >> sys.stderr, "Show not found"
			exit(1)
			
		show.list_data(season=season, episode=episode)
				
	except KeyboardInterrupt:
		print >> sys.stderr, "\nProgram exited without completing"
	
	except RuntimeError:
		exit(1)
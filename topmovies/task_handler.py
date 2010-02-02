import urllib
import logging
import re
import sys
import datetime
import math
from xml.dom import minidom
import xpath

from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue
from django.http import HttpResponse
from django.http import HttpResponseServerError
from django.utils import simplejson
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify

from imdb import IMDb

import gdata.urlfetch
import gdata.service
import gdata.youtube
import gdata.youtube.service
gdata.service.http_request_handler = gdata.urlfetch

from topmovies import models
from topmovies import settings
from topmovies import tm_util

def schedule_refreshes(request):
    logging.info('Scheduling refreshes')
    for source in models.MovieListingSource.all().filter('active = ', True):
        if source.paginate:
            page_count = int(math.ceil(float(source.max_movie_count) / float(settings.MOVIE_REFRESH_QUERY_SIZE)))
            for i in range(0, page_count):
                taskqueue.add(url=reverse('topmovies.task_handler.refresh_movie_source'), 
                    params={'source_key': source.key(), 'offset': i * settings.MOVIE_REFRESH_QUERY_SIZE})
        else:
            taskqueue.add(url=reverse('topmovies.task_handler.refresh_movie_source'), 
                params={'source_key': source.key()})    
    
    #Then we reduce to publish the update, wait 5 mins to publish to ensure map completed, and all list entries loaded
    taskqueue.add(url=reverse('topmovies.task_handler.list_entry_reduce'), countdown=settings.MOVIE_REFRESH_REDUCE_DELAY)    
    
    return HttpResponse('Done')

def refresh_movie_source(request):
    if 'source_key' not in request.REQUEST:
        return HttpResponseServerError('No source key specified in request params')
        
    source = models.MovieListingSource.get(request.REQUEST['source_key'])
    if not source:
        logging.error('Unable to find MovieListingSource: %s', request.REQUEST['source_key'])
        return HttpResponse('Error unable to find Source')
    elif not source.yql:
        logging.error('No yql for MovieListingSource: %s' % str(source))
        return HttpResponse('No YQL for source')
    elif not source.settings:
        logging.error('No settings for MovieListingSource: %s' % str(source))
        return HttpResponse('No settings for source')    
        
    logging.info('Refreshing movie from source %s', str(source))
        
    yql = source.yql
    if 'offset' in request.REQUEST:
        query_offset = int(request.REQUEST['offset']) + 1
        yql = '%s limit %d offset %d' % (yql, settings.MOVIE_REFRESH_QUERY_SIZE, query_offset)
        
    form_data = urllib.urlencode({"q": yql, "format": "xml", "diagnostics": "false"})
    result = urlfetch.fetch(url=settings.YQL_BASE_URL,payload=form_data,method=urlfetch.POST)
    dom = minidom.parseString(result.content)
    
    result_nodes = dom.getElementsByTagName('results')[0].childNodes
    name_nodes = xpath.find(source.settings.name_xpath, dom)
    leaches_nodes = xpath.find(source.settings.leaches_xpath, dom)
    logging.info('Found %d raw names', len(name_nodes))
    
    strip_white_pattern = re.compile(r"\s+")
    source_results = []
    for index, name_node in enumerate(name_nodes):
        logging.debug('Node: ' + result_nodes[index].toxml())
        raw_name = strip_white_pattern.sub(' ', getText(name_node))
        leaches = strip_white_pattern.sub(' ', getText(leaches_nodes[index]))
        logging.info('Raw Name: %s, Leaches: %s', raw_name, leaches)
        source_results.append(models.MovieListEntry(raw_movie_name=raw_name, leaches=int(leaches), active=False))
    
    db.put(source_results)
    
    #Refresh done using map/reduce.  First we map to find the movie details
    for source_result in source_results:
        taskqueue.add(url=reverse('topmovies.task_handler.find_movie'), params={'source_entry_key': source_result.key()})
        
    return HttpResponse("Loaded results for source: %s" % str(source))

def getText(source_node):
    rc = ""
    for node in source_node.childNodes:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc

def find_movie(request):
    if 'source_entry_key' not in request.REQUEST:
        return HttpResponseServerError('No MovieListEntry key  (source_entry_key) key in request params')
        
    source_entry = models.MovieListEntry.get(request.REQUEST['source_entry_key'])
    if not source_entry:
        logging.error('Unable to find MovieListEntry %s', request.REQUEST['source_entry_key'])
        return HttpResponse('Error: Unable to find MovieListEntry')
        
    logging.info('Finding movie for raw name %s' % source_entry.raw_movie_name)
    try:
        movie_name, movie_year = get_movie_details(source_entry.raw_movie_name)
        if not movie_name:
            raise GetMovieException("Unable to find movie name from raw name '%s'" % source_entry.raw_movie_name)
    
        #First check to see if we already have a matching movie
        existing_movie = None
        if movie_year:
            existing_movie = (models.TopMovie.all().filter('other_titles = ', movie_name)
                                                   .filter('year = ', movie_year).get())
        else:
            existing_movie = models.TopMovie.all().filter('other_titles = ', movie_name).get()
    
        if existing_movie:
            logging.info("Found existing movie entity for raw movie name %s", source_entry.raw_movie_name)
            source_entry.movie = existing_movie
            source_entry.put()
            return HttpResponse("Done.  Found existing movie entity: %s" % existing_movie.key())
        
        ia = IMDb('http')
        movies = ia.search_movie(movie_name)
        if not movies:
            raise GetMovieException("Unable to find movie name from name '%s', raw name '%s'" % (movie_name, source_entry.raw_movie_name))
    
        result_movie = None
        for movie in movies:
            logging.info("Found movie '%s' %s [%s] for search '%s'", 
                movie['title'], movie['year'], movie.movieID, movie_name)
            #If we dont have a year we should try to find the highest year value
            if not movie_year or movie_year == movie['year']:
                result_movie = movie
                break
    
        if not result_movie:
            raise GetMovieException("Unable to find imdb movie for raw name '%s' [%s]" % (source_entry.raw_movie_name, source_entry.key()))
    
        logging.info("Found match imdb movie %s", result_movie.movieID)
        existing_movie = models.TopMovie.all().filter('title = ', result_movie['title']).filter('year = ', result_movie['year']).get()
        if existing_movie:
            #Add into other titles so we dont have to hit imdb again
            existing_movie.other_titles.append(movie_name)
            existing_movie.put()
            source_entry.movie = existing_movie
        else:
            logging.info('Adding new movie %s', result_movie['title'])
            #Use slugged movie title and year as key to prevent duplicates
            movie_entity = models.TopMovie(key_name=slugify('%s %d' % (result_movie['title'], result_movie['year'])),
                                title=result_movie['title'],
                                year=result_movie['year'],
                                imdb_id=result_movie.movieID,
                                other_names=[movie_name],
                                active=True,
                                has_image=False)
            movie_entity.put()   
            source_entry.movie = movie_entity
            #Schedule task to download a thumbnail image and try to find a trailer on youtube
            taskqueue.add(url=reverse('topmovies.task_handler.get_movie_image_and_genres'), params={'imdb_id': result_movie.movieID})
            taskqueue.add(url=reverse('topmovies.task_handler.get_movie_trailer'), params={'imdb_id': result_movie.movieID})
        source_entry.put()
    
        return HttpResponse("Done.  Added TopMovie %s" % source_entry.movie.key())
    except GetMovieException, details:
        #Log error details and remove no longer valid cat results
        error_details = str(details)
        logging.warn("Unable to retrive movie details for raw name '%s'\n%s", source_entry.raw_movie_name, error_details)
        #Create a failure entity if one doesnt already exist
        if not models.GetMovieFailure.all().filter('raw_movie_name = ', source_entry.raw_movie_name).count(1):
            failure = models.GetMovieFailure(raw_movie_name=source_entry.raw_movie_name, error_message=error_details)
            failure.put()
        
        source_entry.delete()
        return HttpResponse("Error: %s" % error_details)

def get_movie_image_and_genres(request):
    if 'imdb_id' not in request.REQUEST:
        return HttpResponseServerError('Unable to load movie poster')    
    imdb_id = request.REQUEST['imdb_id']
    movie_image = models.TopMovieImage.all().filter('imdb_id =', imdb_id).get()
    if movie_image:
        logging.info('image entity already exists for %s', imdb_id)
        mark_has_image(imdb_id, True)
        return HttpResponse('Movie already exists')
    logging.info('Get movie image for imdb id %s', imdb_id)
    retries = 0
    if 'retries' in request.REQUEST:
        retries = int(request.REQUEST['retries'])
    
    ia = IMDb('http')
    imdb_movie = ia.get_movie(imdb_id)
    try:
        set_genres(imdb_id, imdb_movie['genres'])
        cover_url = imdb_movie['cover']
        logging.info('Got url %s', cover_url)
        
        #Download the image
        img_data = None
        try:
            img_download = urllib.urlopen(cover_url)
            img_data = img_download.read()
            img_download.close()
        except:
            logging.error('Img fetch for %s failed: %s', cover_url, str(sys.exc_info()[1]))
            if retries < settings.GET_MOVIES_RETRIES:
                taskqueue.add(url=reverse('topmovies.task_handler.get_movie_image'), 
                    params={'imdb_id': result_movie.movieID, 'retries': retries + 1})
            return HttpResponse('Image fetch failed.')    
            
        content_type, width, height = tm_util.getImageInfo(img_data)
        logging.info('Img size %dx%d type %s', width, height, content_type)
        #TODO resize?
        img_entity = models.TopMovieImage(imdb_id=imdb_id,
                    img_data=img_data,
                    content_type=content_type,
                    width = width,
                    height = height)
        img_entity.put()
        mark_has_image(imdb_id, True)
    except:
        logging.warn('Unable to get cover art for %s Reason: %s', str(imdb_movie), str(sys.exc_info()[1])) 
          
    return HttpResponse('Done.')

def mark_has_image(imdb_id, has_image):
    movies = []
    for movie in models.TopMovie.all().filter('imdb_id =', imdb_id):
        movie.has_image = has_image
        movies.append(movie)
    db.put(movies)

def set_genres(imdb_id, genres):
    movies = []
    for movie in models.TopMovie.all().filter('imdb_id =', imdb_id):
        movie.genres = genres
        movies.append(movie)
    db.put(movies)    
    
def retry_missing_images(request):
    query = models.TopMovie.all().filter('has_image = ', False).order('__key__')
    if 'last_key' in request.REQUEST:
        query = models.TopMovie.all().filter('has_image = ', False).filter('__key__ >', db.Key(request.REQUEST['last_key'])).order('__key__')
        
    logging.info('Retrying missing images')
    last_key = None
    for movie in query.fetch(20):
        taskqueue.add(url=reverse('topmovies.task_handler.get_movie_image'), params={'imdb_id': movie.imdb_id})
        last_key = str(movie.key())

    #Keep cycling through movies until we have retried them all
    if last_key:
        taskqueue.add(url=reverse('topmovies.task_handler.retry_missing_images'), params={'last_key': last_key})
        
    return HttpResponse('Done')    

def get_missing_genres(request):
    query = models.TopMovie.all().order('__key__')
    if 'last_key' in request.REQUEST:
        query = models.TopMovie.all().filter('__key__ >', db.Key(request.REQUEST['last_key'])).order('__key__')

    last_key = None
    for movie in query.fetch(1):
        imdb_id = movie.imdb_id
        logging.info('Retrying missing genre for %s', imdb_id)
        ia = IMDb('http')
        imdb_movie = ia.get_movie(imdb_id)
        try:
            set_genres(imdb_id, imdb_movie['genres'])
        except:
            logging.error('Unable to find genres for imdb movie %s', imdb_id)
        last_key = str(movie.key())        

    #Keep cycling through movies until we have retried them all
    if last_key:
        taskqueue.add(url=reverse('topmovies.task_handler.get_missing_genres'), params={'last_key': last_key})

    return HttpResponse('Done for %s' % last_key)

def get_movie_trailer(request):
    if 'imdb_id' not in request.REQUEST:
        return HttpResponseServerError('Unable to load movie poster')
    imdb_id = request.REQUEST['imdb_id']
        
    movie = models.TopMovie.all().filter('imdb_id = ', imdb_id).get()
    if not movie:
        logging.error('Unable to find movie entity for imdb id %s', imdb_id)
        return HttpResponse('Unable to find movie.')
        
    logging.info('Searching for youtube trailer for movie %s [%s]', movie.title, imdb_id)
    #FIXME, youtube search seems to fail within non ascii movie names
    if not is_ascii(movie.title):
        logging.error('Unable to search for movie trailer as non ascii title %s', movie.title)
        return HttpResponse('Fail. Non ascii title')
    client = gdata.youtube.service.YouTubeService()
    client.developer_key = settings.YOUTUBE_DEV_ID
    query = gdata.youtube.service.YouTubeVideoQuery()
    #We only want videos we can embeded
    query.format = '5'
    query.vq = '%s trailer' % (movie.title)
    #query.orderby = 'viewCount'
    query.max_results = '1'
    feed = client.YouTubeQuery(query)
    
    if feed.entry:
        for entry in feed.entry:
            logging.info('Found youtube trailer: %s', entry.media.player.url)
            movie.youtube_url = entry.media.player.url
            break
        movie.put()
    else:
        logging.error('No youtube trailer found for movie %s', movie.title)
        
    return HttpResponse('Done.')

def is_ascii(s):
    return all(ord(c) < 128 for c in s)
    
def get_movie_details(raw_name):
    """Uses regex to extract a movies name and year from a torrent files name"""
    #Strip dots which are normally used instead of spaces
    replace_pattern = re.compile(r"\.")
    clean_name = replace_pattern.sub(' ', raw_name)
    
    torrent_types = ['1080p', '\\d{4}[^p]', '720p', 'DVDRip', 'R5', 'DVDSCR', 'BDRip', '\\s+CAM', '\\sTS\\s', 'PPV']
    name_pattern = re.compile(r'((LiMiTED\s*)?\(?\[?(' + '|'.join(torrent_types) + r')\)?\]?)', re.IGNORECASE)   
    name_match = name_pattern.split(clean_name)
    if not name_match:
        return None, None
    movie_name = name_match[0]
    #If we didnt take anything out of the name than there wasnt a match
    if movie_name == clean_name:
        return None, None
            
    #Check for p so we dont hit 1080p
    year_pattern = re.compile(r'\d{4}(?=[^p])')
    #logging.info('Left over: %s', clean_name[len(movie_name):])
    year_match = year_pattern.search(clean_name[len(movie_name):])
    movie_year = None
    if year_match:
        movie_year = int(year_match.group(0).strip())
    
    return movie_name.strip(), movie_year

def list_entry_reduce(request):
    """Merges list entries for the same item"""
    query = models.MovieListEntry.all().filter('active = ', False).order('__key__')
    if 'last_key' in request.REQUEST:
        query = models.MovieListEntry.all().filter('active = ', False).filter('__key__ >', db.Key(request.REQUEST['last_key'])).order('__key__')
        
    logging.info('reducing list entries')
    last_key = None
    for entry in query.fetch(10):
        last_key = str(entry.key())
        if not entry.movie or not entry.movie.active:
            entry.delete()
            continue
        #Try to find another entry with the same movie (i.e. check to see if the current entry is a duplicate)
        master_entry = models.MovieListEntry.all().filter('active = ', False).filter('movie = ', entry.movie).filter('__key__ <', entry.key()).get()
        if master_entry:
            #If this is a new raw name we assume its a new torrent and therefore the leache tally should be increased
            if entry.raw_movie_name not in master_entry.other_raw_names:
                master_entry.leaches = master_entry.leaches + entry.leaches
                master_entry.other_raw_names.append(entry.raw_movie_name)
            entry.delete()
        else:
            entry.genres = entry.movie.genres
            master_entry = entry
        master_entry.put()

    #Keep cycling through movies until we have retried them all
    if last_key:
        taskqueue.add(url=reverse('topmovies.task_handler.list_entry_reduce'), params={'last_key': last_key})
    else:
        taskqueue.add(url=reverse('topmovies.task_handler.switch_active_list_entries'))
        
    return HttpResponse('Done')

def switch_active_list_entries(request):
    """Switch the active entries to values just loaded"""
    #TODO rewrite this function as it wont scale!
    active_entries = models.MovieListEntry.all().filter('active = ', True).fetch(1000)
    new_entries = []
    for entry in models.MovieListEntry.all().filter('active = ', False):
        entry.active  = True
        new_entries.append(entry)
    
    entry_count = len(new_entries)
    if entry_count:
        db.delete(active_entries)
        db.put(new_entries)
        logging.info('Switched active entries, new active entrie count %d', entry_count)
        return HttpResponse('Done actived %d entries' % entry_count)
    else:
        logging.error('Switch active entries run but no entries to activate found ...')
        return HttpResponse('Error: no entries to activate found.')
    
class GetMovieException(Exception):
    """Exception throw if unable to get movie details from raw movie name"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)    
    
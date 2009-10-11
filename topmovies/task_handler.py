import urllib
import logging
import re
import sys
import datetime
from xml.dom import minidom 

from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue
from django.http import HttpResponse
from django.http import HttpResponseServerError
from django.utils import simplejson
from django.core.urlresolvers import reverse

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
    for category in models.MovieCategory.all().filter('active = ', True):
        for i in range(0, settings.MOVIE_REFRESH_PAGES):
            taskqueue.add(url=reverse('topmovies.task_handler.refresh_movie_category'), 
                params={'category': category.name, 'offset': i * settings.MOVIE_REFRESH_QUERY_SIZE})
    
    return HttpResponse('Done')

def refresh_movie_category(request):
    if 'category' not in request.REQUEST:
        return HttpResponseServerError('No category specified in request params')
        
    category = models.MovieCategory.all().filter('name = ', request.REQUEST['category']).get()
    if not category:
        logging.error('Unable to find Category %s', request.REQUEST['category'])
        return HttpResponse('Error unable to find Category')
    elif not category.yql:
        logging.error('No yql for category %s' % (category.name))
        return HttpResponse('No YQL for category')
    logging.info('Refreshing movie category %s', category.name)
        
    query_offset = 0
    if 'offset' in request.REQUEST:
        query_offset = int(request.REQUEST['offset'])
    form_data = urllib.urlencode({"q": category.yql + ' limit %d offset %d' % (settings.MOVIE_REFRESH_QUERY_SIZE, query_offset), 
                                "format": "xml", "diagnostics": "false"})
    result = urlfetch.fetch(url=settings.YQL_BASE_URL,payload=form_data,method=urlfetch.POST)
    dom = minidom.parseString(result.content) 
    
    strip_white_pattern = re.compile(r"\s+")
    cat_results = []
    for index, raw_result in enumerate(dom.getElementsByTagName('results')[0].childNodes):
        logging.debug('Node: ' + raw_result.toxml())
        raw_name = strip_white_pattern.sub(' ', getText(raw_result.childNodes))
        logging.info('Raw Name [%s]: %s', category.name, raw_name)
        cat_results.append(models.CategoryResult(raw_movie_name=raw_name, category=category, active=False, 
                            order=(query_offset+index+1)))
    
    db.put(cat_results)
    
    #Refresh done using map/reduce.  First we map to find the movie details
    for cat_result in cat_results:
        taskqueue.add(url=reverse('topmovies.task_handler.find_movie'), params={'cat_result': cat_result.key()})
    #Then we reduce to publish the update, wait 5 mins to publish to ensure map completed,
    #however, we only want to do it onces per category so we only add if the offset is 0
    if query_offset == 0:
        taskqueue.add(url=reverse('topmovies.task_handler.refresh_movie_category_reduce'), 
                        params={'category': category.name}, countdown=settings.MOVIE_REFRESH_REDUCE_DELAY)
        
    return HttpResponse("Generated CategoryResult for %s." % (category.name))

def getText(nodelist):
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc

def find_movie(request):
    if 'cat_result' not in request.REQUEST:
        return HttpResponseServerError('No category result (cat_result) key in request params')
        
    cat_result = models.CategoryResult.get(request.REQUEST['cat_result'])
    if not cat_result:
        logging.error('Unable to find CategoryResult %s', request.REQUEST['cat_result'])
        return HttpResponse('Error: Unable to find CategoryResult')
        
    logging.info('Finding movie for raw name %s' % cat_result.raw_movie_name)
    try:
        movie_name, movie_year = get_movie_details(cat_result.raw_movie_name)
        if not movie_name:
            raise GetMovieException("Unable to find movie name from raw name '%s'" % cat_result.raw_movie_name)
    
        #First check to see if we already have a matching movie
        existing_movie = None
        if movie_year:
            existing_movie = models.TopMovie.all().filter('other_titles = ', movie_name).filter('year = ', movie_year).get()
        else:
            existing_movie = models.TopMovie.all().filter('other_titles = ', movie_name).get()
    
        if existing_movie:
            logging.info("Found existing movie entity for raw movie name %s", cat_result.raw_movie_name)
            cat_result.movie = existing_movie
            cat_result.put()
            return HttpResponse("Done.  Found existing movie entity: %s" % existing_movie.key())
        
        ia = IMDb('http')
        movies = ia.search_movie(movie_name)
        if not movies:
            raise GetMovieException("Unable to find movie name from name '%s', raw name '%s'" % (movie_name, cat_result.raw_movie_name))
    
        result_movie = None
        for movie in movies:
            logging.info("Found movie '%s' %s [%s] for search '%s'", 
                movie['title'], movie['year'], movie.movieID, movie_name)
            if not movie_year or movie_year == movie['year']:
                result_movie = movie
                break
    
        if not result_movie:
            raise GetMovieException("Unable to find imdb movie for raw name '%s' [%s]" % (cat_result.raw_movie_name, cat_result.key()))
    
        logging.info("Found match imdb movie %s", result_movie.movieID)
        existing_movie = models.TopMovie.all().filter('title = ', result_movie['title']).filter('year = ', result_movie['year']).get()
        if existing_movie:
            #Add into other titles so we dont have to hit imdb again
            existing_movie.other_titles.append(movie_name)
            existing_movie.put()
            cat_result.movie = existing_movie
        else:
            logging.info('Adding new movie %s', result_movie['title'])
            movie_entity = models.TopMovie(title=result_movie['title'],
                                year=result_movie['year'],
                                imdb_id=result_movie.movieID,
                                other_names=[movie_name])
            movie_entity.put()   
            cat_result.movie = movie_entity
            #Schedule task to download a thumbnail image and try to find a trailer on youtube
            taskqueue.add(url=reverse('topmovies.task_handler.get_movie_image'), params={'imdb_id': result_movie.movieID})
            taskqueue.add(url=reverse('topmovies.task_handler.get_movie_trailer'), params={'imdb_id': result_movie.movieID})
        cat_result.put()
    
        return HttpResponse("Done.  Added TopMovie %s" % cat_result.movie.key())
    except GetMovieException, details:
        #Log error details and remove no longer valid cat results
        error_details = str(details)
        logging.warn("Unable to retrive movie details for raw name '%s'\n%s", cat_result.raw_movie_name, error_details)
        #Create a failure entity if one doesnt already exist
        if not models.GetMovieFailure.all().filter('raw_movie_name = ', cat_result.raw_movie_name).count(1):
            failure = models.GetMovieFailure(raw_movie_name=cat_result.raw_movie_name, error_message=error_details)
            failure.put()
        
        cat_result.delete()
        return HttpResponse("Error: %s" % error_details)

def get_movie_image(request):
    if 'imdb_id' not in request.REQUEST:
        return HttpResponseServerError('Unable to load movie poster')    
    imdb_id = request.REQUEST['imdb_id']
    movie_image = models.TopMovieImage.all().filter('imdb_id =', imdb_id).get()
    if movie_image:
        logging.info('image entity already exists for %s', imdb_id)
        return HttpResponse('Movie already exists')
    logging.info('Get movie image for imdb id %s', imdb_id)
    retries = 0
    if 'retries' in request.REQUEST:
        retries = int(request.REQUEST['retries'])
    
    ia = IMDb('http')
    imdb_movie = ia.get_movie(imdb_id)
    try:
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
    except:
        logging.warn('Unable to get cover art for %s Reason: %s', str(imdb_movie), str(sys.exc_info()[1])) 
          
    return HttpResponse('Done.')

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
    
    torrent_types = ['1080p', '720p', 'DVDRip', 'R5', 'DVDSCR', 'BDRip', '\\s+CAM']
    name_type_pattern = re.compile(r'[^\(\[]+(?=(\(?\[?(' + '|'.join(torrent_types) + r')\)?\]?))', re.IGNORECASE)
    name_year_pattern = re.compile(r'[^\(\[]+(?=(\(?\[?\d{4}\)?\]?))')

    #Combining year and type into a single pattern doesnt seem to work as some torrent names
    #have year then type and combined pattern seems to include the year as part of the name
    name_type_match = name_type_pattern.match(clean_name)
    name_year_match = name_year_pattern.match(clean_name)
    
    movie_name = None
    if not name_type_match and not name_year_match:
        return None, None
    elif not name_type_match:
        movie_name = name_year_match.group(0)
    elif not name_year_match:
        movie_name = name_type_match.group(0)
    else:
        year_movie_name = name_year_match.group(0)
        type_movie_name = name_type_match.group(0)
        logging.debug('Year: "%s" Type: "%s"', year_movie_name, type_movie_name)
        #We want to shortest one as the longer one will contain the year or type and we only want the name
        if len(year_movie_name) < len(type_movie_name):
            movie_name = year_movie_name
        else:
            movie_name = type_movie_name
            
    #Check for p so we dont hit 1080p
    year_pattern = re.compile(r'\d{4}(?=[^p])')
    #logging.info('Left over: %s', clean_name[len(movie_name):])
    year_match = year_pattern.search(clean_name[len(movie_name):])
    movie_year = None
    if year_match:
        movie_year = int(year_match.group(0).strip())
    
    return movie_name.strip(), movie_year

def refresh_movie_category_reduce(request):    
    if 'category' not in request.REQUEST:
        return HttpResponseServerError('No category specified in request params')
    logging.info('Refresh movie reduce for %s', request.REQUEST['category'])
        
    category = models.MovieCategory.all().filter('name = ', request.REQUEST['category']).get()
    if not category:
        logging.error('Unable to find Category %s', request.REQUEST['category'])
        return HttpResponse('Error unable to find Category')
    logging.info('Mapping movie %s category refresh', category.name)
    
    #First get all active results for removal
    active_results = models.CategoryResult.all().filter('active = ', True).filter('category = ', category).fetch(100)
    #Now remove any duplicates and mark active
    save_results = []
    movies = []
    duplicate_results = []
    for cat_result in models.CategoryResult.all().filter('active = ', False).filter('category = ', category):
        if not cat_result.movie:
            continue
        elif cat_result.movie in movies:
            duplicate_results.append(cat_result)
        else:
            movies.append(cat_result.movie)
            cat_result.active = True
            save_results.append(cat_result)
            
    db.delete(duplicate_results)
    db.put(save_results)
    movie_count = len(save_results)
    #Now safe to remove active result
    db.delete(active_results)
    
    category.last_refreshed = datetime.datetime.today()
    category.put()
    
    logging.info('Mapped movie %s category found %d movies', category.name, movie_count)
    return HttpResponse("Done. %d results for category %s" % (movie_count, category.name))
    
    
class GetMovieException(Exception):
    """Exception throw if unable to get movie details from raw movie name"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)    
    
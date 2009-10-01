import urllib
import logging
import re
import sys
import datetime

from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue
from django.http import HttpResponse
from django.http import HttpResponseServerError
from django.utils import simplejson
from django.core.urlresolvers import reverse

from imdb import IMDb

from topmovies import models
from topmovies import settings

def schedule_refreshes(request):
    logging.debug('Scheduling refreshes')
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
    logging.debug('Refreshing movie category %s', category.name)
        
    query_offset = 0
    if 'offset' in request.REQUEST:
        query_offset = int(request.REQUEST['offset'])
    form_data = urllib.urlencode({"q": category.yql + ' limit %d offset %d' % (settings.MOVIE_REFRESH_QUERY_SIZE, query_offset), 
                                "format": "json"})
    result = urlfetch.fetch(url=settings.YQL_BASE_URL,payload=form_data,method=urlfetch.POST)
    fetch_result = simplejson.loads(result.content)
    
    strip_white_pattern = re.compile(r"\s+")
    cat_results = []
    for index, raw_result in enumerate(fetch_result['query']['results']['a']):
        if 'content' not in raw_result:
            continue
        raw_name = strip_white_pattern.sub(' ', raw_result['content'])
        logging.debug('Raw Name [%s]: %s', category.name, raw_name)
        cat_results.append(models.CategoryResult(raw_movie_name=raw_name, category=category, active=False, order=index))
    
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

def find_movie(request):
    if 'cat_result' not in request.REQUEST:
        return HttpResponseServerError('No category result (cat_result) key in request params')
        
    cat_result = models.CategoryResult.get(request.REQUEST['cat_result'])
    if not cat_result:
        logging.error('Unable to find CategoryResult %s', request.REQUEST['cat_result'])
        return HttpResponse('Error: Unable to find CategoryResult')
        
    logging.debug('Finding movie for raw name %s' % cat_result.raw_movie_name)
    try:
        movie_name, movie_year = get_movie_details(cat_result.raw_movie_name)
        if not movie_name:
            raise GetMovieException("Unable to find movie name from raw name '%s'" % cat_result.raw_movie_name)
    
        #First check to see if we already have a matching movie
        existing_movie = None
        if movie_year:
            existing_movie = models.TopMovie.all().filter('title = ', movie_name).filter('year = ', movie_year).get()
        else:
            existing_movie = models.TopMovie.all().filter('title = ', movie_name).get()
    
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
            logging.debug("Found movie '%s' %s [%s] for search '%s'", 
                movie['title'], movie['year'], movie.movieID, movie_name)
            if not movie_year or movie_year == movie['year']:
                #Get additional details about movie as match
                result_movie = ia.get_movie(movie.movieID)
                #result_movie = movie
                break
    
        if not result_movie:
            raise GetMovieException("Unable to find imdb movie for raw name '%s' [%s]" % (cat_result.raw_movie_name, cat_result.key()))
    
        logging.info("Found match imdb movie %s", result_movie.movieID)
        existing_movie = models.TopMovie.all().filter('title = ', result_movie['title']).filter('year = ', result_movie['year']).get()
        if existing_movie:
            cat_result.movie = existing_movie
        else:
            logging.debug('Adding new movie %s', result_movie['title'])
            cover_url = None
            if 'cover url' in result_movie:
                cover_url = result_movie['cover url']
            else:
                logging.warn('No cover art found for ' + str(result_movie))
            movie_entity = models.TopMovie(title=result_movie['title'],
                                year=result_movie['year'],
                                imdb_id=result_movie.movieID,
                                image_link=cover_url)
            movie_entity.put()   
            cat_result.movie = movie_entity
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
    
def get_movie_details(raw_name):
    """Uses regex to extract a movies name and year from a torrent files name"""
    replace_pattern = re.compile(r"\.")
    clean_name = replace_pattern.sub(' ', raw_name)
    
    name_pattern = re.compile(r'[^\(\[]+(?=(1080p|\(\d{4}\)|\[\d{4}\]|\d{4}|DVDRip|720p|R5|DVDSCR|BDRip|\s+CAM))')
    year_pattern = re.compile(r'\d{4}(?=[^p])')
    
    match = name_pattern.match(clean_name)
    if not match:
        return None, None
    movie_name = match.group(0)
    
    #logging.debug('Left over: %s', clean_name[len(movie_name):])
    year_match = year_pattern.search(clean_name[len(movie_name):])
    movie_year = None
    if year_match:
        movie_year = int(year_match.group(0).strip())
    
    return movie_name.strip(), movie_year

def refresh_movie_category_reduce(request):    
    if 'category' not in request.REQUEST:
        return HttpResponseServerError('No category specified in request params')
        
    category = models.MovieCategory.all().filter('name = ', request.REQUEST['category']).get()
    if not category:
        logging.error('Unable to find Category %s', request.REQUEST['category'])
        return HttpResponse('Error unable to find Category')
    logging.debug('Mapping movie %s category refresh', category.name)
    
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
    
    logging.debug('Mapped movie %s category found %d movies', category.name, movie_count)
    return HttpResponse("Done. %d results for category %s" % (movie_count, category.name))
    
    
class GetMovieException(Exception):
    """Exception throw if unable to get movie details from raw movie name"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)    
    
import string
import logging

from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from ragendja.template import render_to_response
from django.http import Http404
from django import conf
from django.utils import simplejson

from topmovies import models

def index(request):
    results = []
    #TODO add pagination or random ness
    for category in models.MovieCategory.all().filter('active = ', True).order('order').fetch(5):
        count = get_movie_count(category)
        if count:
            results.append({'category': category, 'movie_count': count})
            
    return render_to_response(request, 'index.html', {'categories': results})

def categories(request):
    return render_to_response(request, 'categories.html', 
        {'categories': models.MovieCategory.all().filter('active = ', True).order('name')})

def movie_category(request, category_name):
    #Fix cat name so matched, imdb format, most hackiness needed for Sci-Fi
    category_name = string.capwords(category_name.replace('-', '- ')).replace('- ', '-')
    logging.info('Cat name %s', category_name)    
    category = models.MovieCategory.all().filter('name = ', category_name).get()
    if not category:
        raise Http404
    
    movie_count = get_movie_count(category)
            
    return render_to_response(request, 'category_list.html', {'category': category, 'movie_count': movie_count})

def get_movie_count(category):
    return (models.MovieListEntry.all().filter('genres =', category.name)
                                       .filter('active =', True)
                                       .count(300))

def all_movies(request):
    movie_count = models.MovieListEntry.all().filter('active =', True).count(1000)
    #Bit of a hack to let us use the existing template
    all_category = models.MovieCategory(name='all')
    return render_to_response(request, 'category_list.html', {'category': all_category, 'movie_count': movie_count})

def all_movies_as_json(request):
    offset, page_size = get_offset_and_page_size(request)
    
    entries = []
    if offset:
        entries = (models.MovieListEntry.all().filter('active =', True)
                                          .filter('leaches <', offset)
                                          .order('-leaches')
                                          .fetch(page_size))
    else:
        entries = (models.MovieListEntry.all().filter('active =', True)
                                          .order('-leaches')
                                          .fetch(page_size))
    
    return HttpResponse(simplejson.dumps(movies_as_json_map(entries)),content_type="application/json")

def get_movies_as_json(request, category_name):
    category = models.MovieCategory.all().filter('name = ', category_name).get()
    if not category:
        raise Http404
    
    offset, page_size = get_offset_and_page_size(request)
    
    entries = []
    if offset:
        entries = (models.MovieListEntry.all().filter('genres =', category.name)
                                              .filter('active =', True)
                                              .filter('leaches <', offset)
                                              .order('-leaches')
                                              .fetch(page_size))
    else:
        entries = (models.MovieListEntry.all().filter('genres =', category.name)
                                              .filter('active =', True)
                                              .order('-leaches')
                                              .fetch(page_size))
    
    return HttpResponse(simplejson.dumps(movies_as_json_map(entries)),content_type="application/json")                    

def get_offset_and_page_size(request):
    offset = 0
    if 'offset' in request.REQUEST:
        offset = int(request.REQUEST['offset'])
    logging.info('offset %d', offset)
    page_size = 10
    if 'pageSize' in request.REQUEST:
        page_size = int(request.REQUEST['pageSize'])
    
    return offset, page_size

def movies_as_json_map(entries):
    results = []
    for entry in entries:
        results.append({'title'      : entry.movie.title,
                        'year'       : entry.movie.year,
                        'imdb_id'    : entry.movie.imdb_id,
                        'youtube_url': entry.movie.youtube_url,
                        'key'        : str(entry.movie.key()),
                        'order'      : entry.leaches})
    
    return results    
    
def get_movie_image(request, imdb_id):
    movie_image = models.TopMovieImage.all().filter('imdb_id =', imdb_id).get()
    if not movie_image:
        return HttpResponseRedirect(conf.settings.MEDIA_URL + 'topmovies/no_preview.jpg')   
    
    return HttpResponse(content=movie_image.img_data, mimetype=movie_image.content_type)
    

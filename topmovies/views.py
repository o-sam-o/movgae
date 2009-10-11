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
    for category in models.MovieCategory.all().filter('active = ', True).fetch(5):
        count = get_movie_count(category)
        if count:
            results.append({'category': category, 'movie_count': count})
            
    return render_to_response(request, 'index.html', {'categories': results})

def categories(request):
    return render_to_response(request, 'categories.html', 
        {'categories': models.MovieCategory.all().filter('active = ', True).order('name')})

def movie_category(request, category_name):
    category = models.MovieCategory.all().filter('name = ', category_name).get()
    if not category:
        raise Http404
    
    movie_count = get_movie_count(category)
            
    return render_to_response(request, 'category_list.html', {'category': category, 'movie_count': movie_count})

def get_movie_count(category):
    return (models.CategoryResult.all().filter('category =', category)
                                       .filter('active =', True)
                                       .order('order')
                                       .count(300))

def get_movies_as_json(request, category_name):
    category = models.MovieCategory.all().filter('name = ', category_name).get()
    if not category:
        raise Http404
    
    offset = 0
    if 'offset' in request.REQUEST:
        offset = int(request.REQUEST['offset'])
    page_size = 10
    if 'pageSize' in request.REQUEST:
        page_size = int(request.REQUEST['pageSize'])
    
    cat_results = (models.CategoryResult.all().filter('category =', category)
                                         .filter('active =', True)
                                         .filter('order >', offset)
                                         .order('order')
                                         .fetch(page_size))
    
    results = []
    for cat_result in cat_results:
        results.append({'title'      : cat_result.movie.title,
                        'year'       : cat_result.movie.year,
                        'imdb_id'    : cat_result.movie.imdb_id,
                        'youtube_url': cat_result.movie.youtube_url,
                        'key'        : str(cat_result.movie.key()),
                        'order'      : cat_result.order})
    
    return HttpResponse(simplejson.dumps(results),content_type="application/json")                    
    
def get_movie_image(request, imdb_id):
    movie_image = models.TopMovieImage.all().filter('imdb_id =', imdb_id).get()
    if not movie_image:
        return HttpResponseRedirect(conf.settings.MEDIA_URL + 'topmovies/no_preview.jpg')   
    
    return HttpResponse(content=movie_image.img_data, mimetype=movie_image.content_type)
    

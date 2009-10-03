from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from ragendja.template import render_to_response
from django.http import Http404
from django import conf

from topmovies import models

def index(request):
    #TODO add pagination
    categories = models.MovieCategory.all().filter('active = ', True).fetch(10)
            
    return render_to_response(request, 'index.html', {'categories': categories})

def movie_category(request, category_name):
    category = models.MovieCategory.all().filter('name = ', category_name).get()
    if not category:
        raise Http404
    
    movies = models.CategoryResult.all().filter('category =', category).filter('active =', True).order('order').fetch(50)
            
    return render_to_response(request, 'category_list.html', {'category': category, 'movies': movies})
    
def get_movie_image(request, imdb_id):
    movie_image = models.TopMovieImage.all().filter('imdb_id =', imdb_id).get()
    if not movie_image:
        return HttpResponseRedirect(conf.settings.MEDIA_URL + 'topmovies/no_preview.jpg')   
    
    return HttpResponse(content=movie_image.img_data, mimetype=movie_image.content_type)
    

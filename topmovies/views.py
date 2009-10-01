from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from ragendja.template import render_to_response
from django.http import Http404

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
    

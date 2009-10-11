from topmovies import models

def add_categories(request):
    categories = models.MovieCategory.all().filter('active = ', True).order('order').fetch(5)
    additions = {
            'menu_categories': categories,
    }
    return additions
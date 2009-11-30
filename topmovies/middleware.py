import os
import logging
from topmovies import models

def add_categories(request):
    categories = models.MovieCategory.all().filter('active = ', True).order('order').fetch(5)
    additions = {
            'menu_categories': categories,
            'is_prod': is_prod_env(),
            'app_version' : os.environ['CURRENT_VERSION_ID'].split('.')[0],
    }
    return additions
    
def is_dev_env():
    """Returns true if app is currently on dev server"""
    return os.environ.get('SERVER_SOFTWARE','').startswith('Devel')

def is_prod_env():
    """Returns true if the app is currently deployed to the prod server"""
    return not is_dev_env()    
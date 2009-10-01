# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _
from google.appengine.ext import db

class BaseEntity(db.Model):
    """Base entity that all other bbz entities should extend"""
    def id(self):
        return self.key().id()
        
        
class MovieCategory(BaseEntity):
    """A movie category available for display on the site"""
    name = db.StringProperty()
    yql = db.StringProperty()
    
    active = db.BooleanProperty()
    last_refreshed = db.DateTimeProperty()
    
    def __unicode__(self):
        return self.name
    
    
class TopMovie(BaseEntity):
    """A single popular movie"""
    title = db.StringProperty()
    #TODO add support for alterative names
    year = db.IntegerProperty()
    
    imdb_id = db.StringProperty()
    image_link = db.LinkProperty()
    trailer_link = db.LinkProperty()
    
    last_refreshed = db.DateTimeProperty(auto_now_add=True)
    
    def __unicode__(self):
        return "%s (%s)" % (self.title, self.year)
    
    
class CategoryResult(BaseEntity):
    """Result of a movie category search"""
    raw_movie_name = db.StringProperty()
    order = db.IntegerProperty()
    movie = db.ReferenceProperty(TopMovie)
    category = db.ReferenceProperty(MovieCategory)
    active = db.BooleanProperty()
    
    date_created = db.DateTimeProperty(auto_now_add=True)
    
    def __unicode__(self):
        if self.movie:
            return "%s (%s) - %s" % (self.movie.title, self.movie.year, self.category.name)
        else:
            return "%s - %s" % (self.raw_movie_name, self.category.name)

            
class GetMovieFailure(BaseEntity):
    """Log details of movie we couldnt get the name for"""
    raw_movie_name = db.StringProperty()
    error_message = db.StringProperty()
    date_created = db.DateTimeProperty(auto_now_add=True)
    
    def __unicode__(self):
        return self.raw_movie_name
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
    #A list of other possible names, should reduce server load and resolve duplicates
    other_titles = db.StringListProperty()
    year = db.IntegerProperty()
    
    imdb_id = db.StringProperty()
    youtube_url = db.LinkProperty()
    
    last_refreshed = db.DateTimeProperty(auto_now_add=True)
    
    def __unicode__(self):
        return "%s (%s)" % (self.title, self.year)

    #TODO is it possible to do this using the property builtin?
    def put(self):
        """Overwriting standard put the title in other_titles"""
        if not self.other_titles:
            self.other_titles = []
        if self.title not in self.other_titles:
            self.other_titles.append(self.title)
            
        return db.Model.put(self)


class TopMovieImage(BaseEntity):
    imdb_id = db.StringProperty()
    img_data = db.BlobProperty()
    width = db.IntegerProperty()
    height = db.IntegerProperty()
    content_type = db.StringProperty()

    def __unicode__(self):
        return "%s (%s)" % (self.imdb_id, self.content_type)                
    
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
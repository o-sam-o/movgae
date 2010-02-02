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
    
    active = db.BooleanProperty()
    order = db.IntegerProperty()
    
    def __unicode__(self):
        return "%s (%s)" % (self.name, self.order)

    class Meta:
        verbose_name_plural = "Movie categories"    
    
class TopMovie(BaseEntity):
    """A single popular movie"""
    title = db.StringProperty()
    #A list of other possible names, should reduce server load and resolve duplicates
    other_titles = db.StringListProperty()
    year = db.IntegerProperty()
    genres = db.StringListProperty()
    
    imdb_id = db.StringProperty()
    youtube_url = db.LinkProperty()
    has_image = db.BooleanProperty()
    
    active = db.BooleanProperty()
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
        

class MovieListingSettings(BaseEntity):
    "Common settings shared amounts movie listing soures"
    site_name = db.StringProperty()
    name_xpath = db.StringProperty()
    leaches_xpath = db.StringProperty()

    def __unicode__(self):
        return "%s" % (self.site_name)

    class Meta:
        verbose_name_plural = "Movie listing settings"            

class MovieListingSource(BaseEntity):
    """A data source for movie listings, yql is used to extract torrent names"""
    name = db.StringProperty()
    yql = db.StringProperty()  
    #Should the yql be paged   
    paginate = db.BooleanProperty()
    #How many items can we scrap from the page? Used to determine how many pages
    max_movie_count = db.IntegerProperty()
    settings = db.ReferenceProperty(MovieListingSettings)
    active = db.BooleanProperty()

    def __unicode__(self):
        return "%s [%s]" % (self.settings.site_name, self.name)
    
    
class MovieListEntry(BaseEntity):
    """Result of a movie category search"""
    raw_movie_name = db.StringProperty()
    # List of other raw names (torrents) for this movie, used to remove duplicates
    other_raw_names = db.StringListProperty()
    # Used for ranking
    leaches = db.IntegerProperty()
    
    movie = db.ReferenceProperty(TopMovie)
    genres = db.StringListProperty()
    
    active = db.BooleanProperty()
    date_created = db.DateTimeProperty(auto_now_add=True)

    def put(self):
        """Overwriting standard put the title in other_titles"""
        if not self.other_raw_names:
            self.other_raw_names = []
        if self.raw_movie_name not in self.other_raw_names:
            self.other_raw_names.append(self.raw_movie_name)
            
        if self.movie:
            self.genres = self.movie.genres
        
        return db.Model.put(self)
        
    def __unicode__(self):
        if self.movie:
            return "%s (%s) - %s" % (self.movie.title, self.movie.year, self.genres)
        else:
            return "%s - %s" % (self.raw_movie_name, self.leaches)

    class Meta:
        verbose_name_plural = "Movie list entries"

         
class GetMovieFailure(BaseEntity):
    """Log details of movie we couldnt get the name for"""
    raw_movie_name = db.StringProperty()
    error_message = db.StringProperty()
    date_created = db.DateTimeProperty(auto_now_add=True)
    
    def __unicode__(self):
        return self.raw_movie_name
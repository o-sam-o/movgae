from django.contrib import admin
from topmovies.models import MovieCategory, TopMovie, CategoryResult, GetMovieFailure

admin.site.register(TopMovie)
admin.site.register(MovieCategory)
admin.site.register(CategoryResult)
admin.site.register(GetMovieFailure)
from django.contrib import admin
from topmovies import models

admin.site.register(models.TopMovie)
admin.site.register(models.MovieCategory)
admin.site.register(models.CategoryResult)
admin.site.register(models.GetMovieFailure)
admin.site.register(models.TopMovieImage)
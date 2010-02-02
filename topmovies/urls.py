from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    ('^task/refreshAll/$', 'topmovies.task_handler.schedule_refreshes'),
    ('^task/refresh/$', 'topmovies.task_handler.refresh_movie_source'),
    ('^task/getMovieInfo/$', 'topmovies.task_handler.get_movie_image_and_genres'),
    ('^task/getTrailer/$', 'topmovies.task_handler.get_movie_trailer'),
    ('^task/refresh/reduce/$', 'topmovies.task_handler.list_entry_reduce'),
    ('^task/refresh/finalise/$', 'topmovies.task_handler.switch_active_list_entries'),
    ('^task/find/$', 'topmovies.task_handler.find_movie'),
    ('^task/retryImages/$', 'topmovies.task_handler.retry_missing_images'),
    ('^task/retryGenres/$', 'topmovies.task_handler.get_missing_genres'),

    ('^movie/(?P<imdb_id>\w+).jpg$', 'topmovies.views.get_movie_image'),
    ('^about/$', 'django.views.generic.simple.direct_to_template',
        {'template': 'about.html'}),
    ('^categories/$', 'topmovies.views.categories'),
    ('^(?P<category_name>[\w-]+)/json/$', 'topmovies.views.get_movies_as_json'),
    ('^(?P<category_name>[\w-]+)/$', 'topmovies.views.movie_category'),

    (r'^$', 'topmovies.views.index'),
)
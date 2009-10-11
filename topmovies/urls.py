from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    ('^task/refreshAll/$', 'topmovies.task_handler.schedule_refreshes'),
    ('^task/refresh/$', 'topmovies.task_handler.refresh_movie_category'),
    ('^task/getPoster/$', 'topmovies.task_handler.get_movie_image'),
    ('^task/getTrailer/$', 'topmovies.task_handler.get_movie_trailer'),
    ('^task/refresh/reduce/$', 'topmovies.task_handler.refresh_movie_category_reduce'),
    ('^task/find/$', 'topmovies.task_handler.find_movie'),

    ('^movie/(?P<imdb_id>\w+).jpg$', 'topmovies.views.get_movie_image'),
    ('^about/$', 'django.views.generic.simple.direct_to_template',
        {'template': 'about.html'}),
    ('^categories/$', 'topmovies.views.categories'),
    ('^(?P<category_name>\w+)/json/$', 'topmovies.views.get_movies_as_json'),
    ('^(?P<category_name>\w+)/$', 'topmovies.views.movie_category'),

    (r'^$', 'topmovies.views.index'),
)
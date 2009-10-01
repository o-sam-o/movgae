from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    ('^task/refreshAll/$', 'topmovies.task_handler.schedule_refreshes'),
    ('^task/refresh/$', 'topmovies.task_handler.refresh_movie_category'),
    ('^task/refresh/reduce/$', 'topmovies.task_handler.refresh_movie_category_reduce'),
    ('^task/find/$', 'topmovies.task_handler.find_movie'),

    ('^(?P<category_name>\w+)/$', 'topmovies.views.movie_category'),

    (r'^$', 'topmovies.views.index'),
)
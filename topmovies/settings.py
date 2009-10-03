from ragendja.settings_post import settings
settings.add_app_media('movie_style.css',
    'topmovies/movie_style.css',
)

YQL_BASE_URL = 'http://query.yahooapis.com/v1/public/yql'
MOVIE_REFRESH_QUERY_SIZE = 30
MOVIE_REFRESH_PAGES = 3
MOVIE_REFRESH_REDUCE_DELAY = 5*60
GET_MOVIE_IMAGE_RETRIES = 3

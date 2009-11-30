from ragendja.settings_post import settings
settings.add_app_media('movie_style.css',
    'topmovies/movie_style.css',
)

settings.add_app_media('topmovies.js',
    'topmovies/topmovies.js',
)

settings.add_app_media('MovieCarousel.js',
    'topmovies/MovieCarousel.js',
)

settings.add_app_media('topmovies/theme/style.css',
    'topmovies/theme/style.css',
)

settings.add_app_media('topmovies/theme/options/header-default.css',
    'topmovies/theme/options/header-default.css',
)

settings.add_app_media('topmovies/theme/options/content-default.css',
    'topmovies/theme/options/content-default.css',
)

settings.add_app_media('topmovies/theme/js/arclite.js',
    'topmovies/theme/js/arclite.js',
)

settings.add_app_media('topmovies/theme/js/jquery.js',
    'topmovies/theme/js/jquery.js',
)

settings.add_app_media('topmovies/lightbox/jquery.prettyPhoto.js',
    'topmovies/lightbox/jquery.prettyPhoto.js',
)

settings.add_app_media('topmovies/lightbox/prettyPhoto.css',
    'topmovies/lightbox/prettyPhoto.css',
)

YQL_BASE_URL = 'http://query.yahooapis.com/v1/public/yql'
MOVIE_REFRESH_QUERY_SIZE = 30
MOVIE_REFRESH_PAGES = 3
MOVIE_REFRESH_REDUCE_DELAY = 5*60
GET_MOVIE_IMAGE_RETRIES = 3
YOUTUBE_DEV_ID = 'AI39si6d806wGtogD484uERKmZ95OPqoBD2jo8Ick_jWSw0aS41LU9vlLDenSkRg13clIewoRO2FwKBHgaIZ7JueIh72tbGsCQ'

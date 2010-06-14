# Movgae
Overview
--------
This is a short two week project I completed to find popular movies based on torrent stats.  The app is currently deployed at [http://filmclould.appspot.com](http://filmclould.appspot.com).  This project was just hacked together, please excuse the quality of the code.

Features
--------
 * Scrap torrent search sites for popular movies
 * Scrap IMDB for poster + info on movies
 * Display movies using a Javascript carousel, grouping movies by genre and ordering by swarm size 
 * Movie trailer sourced from YouTube and embed in the page
 * YQL + XPath admin interface for adding new source torrent sites.

Technologies
------------
 * Python
 * Django
 * GAE
 * YQL
 * ImdbPy
 * GData API (YouTube)
 * YUI

Setup
-----
The project is designed for deployment on [AppEngine](http://code.google.com/appengine/) please review their documentation for deployment instructions.  Once deployed hit: http://{YOUR APP}.appspot.com/admin, you should be asked to login with your google username and password.  Once inside you will need to setup listing settings, movie sources and categories.

_Movie Listing Settings:_ The settings consist of two xpath, used to extract the torrent name and leach count from the YQL result.  

E.g. for The Pirate Bay 

Name XPath:

	//a[starts-with(@href, "/torrent")]


Leaches XPath:
	
	//td[4]/p
	
_Movie Listing Sources:_ This is a YQL query used to scrap a torrent site, it should be paired with a movie listing setting.

E.g. The Pirate Bay YQL:

	select * from html where url="http://thepiratebay.org/browse/201/0/9" and xpath='//table[@id="searchResult"]/tr'

_Categories:_ These are used to group movies on the home page, they are sourced from IMDB genres.
	
Licence
-------
MIT

Contact
-------
Sam Cavenagh [cavenaghweb@hotmail.com](mailto:cavenaghweb@hotmail.com)
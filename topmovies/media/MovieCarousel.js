function MovieCarousel (category, container, movieCount, xSize, ySize, mediaUrl) {
    var carousel;
    var offset = 0;
    
    function init(){
        carousel = new YAHOO.widget.Carousel(container, 
                                    {animation: { speed: 0.5, effect: YAHOO.util.Easing.easeOut }, 
									 numVisible: [xSize, ySize],
									 numItems: movieCount});
		carousel.on("loadItems", getMovies);
		carousel.render();
		getMovies();	
    }
    YAHOO.util.Event.addListener(window, "load", init);
    
    function getMovieNode(movieDetails) {
		var movieNode = "<div class=\"movieWrapperDiv\">"+
		"<div class=\"movieTitle\">"+
		
		"	<a href=\"http://www.imdb.com/title/tt" + movieDetails.imdb_id + "\">";
		if(movieDetails.title.length > 23){
		movieNode = movieNode + "<span id=\"title-" + movieDetails.key + "\">" + movieDetails.title.substring(0, 20) + "...</span>"+
		"			<script>" +
		"				new YAHOO.widget.Tooltip(\"tt-" + movieDetails.key + "\", "+
		"					{ context:\"title-" + movieDetails.key + "\", text:\"" + movieDetails.title + "\" });"+
		"			</script>";
	    }else{
		    movieNode = movieNode + movieDetails.title;
	    }
		movieNode = movieNode + "	</a>" + 
		
		"</div>"+
		"<div class=\"movieYear\">"+
		movieDetails.year +
		"</div>"+
		
		"<div class=\"moviePosterDiv\">";
	    if (movieDetails.youtube_url){
		movieNode = movieNode + "<a href=\"" + movieDetails.youtube_url + "\" rel=\"prettyPhoto\" title=\"" + movieDetails.title + " Trailer\">"+
		"			<img src=\"/movie/" + movieDetails.imdb_id + ".jpg\" class=\"hasTrailer\"/>"+
		"		</a>";
	    }else{
		movieNode = movieNode + "<img src=\"/movie/" + movieDetails.imdb_id + ".jpg\" class=\"noTrailer\"/>";
	    }
		movieNode = movieNode + "</div>";
		if (showEditLink){
		movieNode = movieNode + "	<div class=\"editLink\">"+
		"		<a href=\"/admin/topmovies/topmovie/" + movieDetails.key + "\">"+
		"			<img src=\"" + mediaUrl + "topmovies/edit_icon.png\"/>"+
		"		</a>"+
		"	</div>";
	    }		
		if (movieDetails.youtube_url){
		movieNode = movieNode + "	<div class=\"youtubeLink\">"+
		"		<a href=\"" + movieDetails.youtube_url + "\" target='_blank'>"+
		"			<img src=\"" + mediaUrl + "topmovies/youtube_icon.png\"/>"+
		"		</a>"+
		"	</div>";
	    }
		movieNode = movieNode + "<div class=\"imdbLink\">"+
		"<a href=\"http://www.imdb.com/title/tt" + movieDetails.imdb_id + "\" target='_blank'>"+
		"		<img src=\"" + mediaUrl + "topmovies/imdb_icon.png\"/>"+
		"	</a>"+
		"</div>"+
		"<div class=\"customLink\">"+
		"	<a class=\"customLinkLink fakeLink\" movieTitle=\"" + movieDetails.title + "\">"+
		"		<img src=\"" + mediaUrl + "topmovies/custom_icon.png\"/>"+
		"	</a>"+
		"</div>"+
		"</div>"
		
		return movieNode;
    }

    function getMovies(o) {
        var pageSize = xSize * ySize;
        //Handle jumping multiple pages
        if(o){
            //YAHOO.log('Num: ' + o.num + " First: " + o.first + " Last: " + o.last);   
            pageSize = o.num;
        }  
        YAHOO.util.Connect.asyncRequest("GET", "/" + category + "/json/?offset="+offset+"&pageSize=" + pageSize,
                {
                    success: function (o) {
                        var results = YAHOO.lang.JSON.parse(o.responseText);
                            
                        for (var i = 0; i < results.length; i++){ 
                            var movieDetails = results[i];
                            YAHOO.log('Got Movie[' + category + ']: ' + movieDetails.title);
                			carousel.addItem(getMovieNode(movieDetails));
                			//Update order which is used for pagination
                			if(offset == 0 || movieDetails.order < offset){
                			    offset = movieDetails.order;
                			}
            			}
            			carousel.show();
            					
            			//Init trailer lightbox
            			jQuery("a[rel^='prettyPhoto']").prettyPhoto();
            			
            			//Init custom links
            			setCustomLinks();
            			
            			//Init no trailer tooltip
                	    var noTrailerNodes = YAHOO.util.Selector.query("img[class~='noTrailer']");
                	    var noTrailerTT = new YAHOO.widget.Tooltip("noTrailerTT", { context:noTrailerNodes, text:"No trailer available" });            			
                    },

                    failure: function (o) {
                        YAHOO.log("Get movies failed: " + o.status);
                        //alert("Ajax request failed!");
                    }
        });
    }
}
function setCustomLinks(){
	var customLinkNodes = YAHOO.util.Selector.query("a[class~='customLinkLink']");
	var customLink = YAHOO.util.Cookie.get("customLinkKey");
	if(customLink){
		for (var i = 0; i < customLinkNodes.length; i++){ 
			var linkNode = customLinkNodes[i];
			var movieTitle = linkNode.getAttribute('movieTitle');
			//YAHOO.log(customLink + ' ' + movieTitle);
			linkNode.href = customLink.replace('%TITLE%', movieTitle);
			linkNode.target = '_blank';
		}
		//No need to display config dialog on config anymore
		YAHOO.util.Event.removeListener(customLinkNodes, "click", showCustomLinkDialog); 
	}else{
		YAHOO.log("Didnt init custom link as non set"); 
		YAHOO.util.Event.on(customLinkNodes, 'click', showCustomLinkDialog); 		
	}
}
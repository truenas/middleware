define([], function(){
	function has(){
		return !document.createStyleSheet;
	}
	var head = document.head;
	return function insertCss(css){
		if(has("dom-create-style-element")){
			// we can use standard <style> element creation
			styleSheet = document.createElement("style");
			styleSheet.setAttribute("type", "text/css");
			styleSheet.appendChild(document.createTextNode(css));
			head.insertBefore(styleSheet, head.firstChild);
			return styleSheet;
		}
		else{
			var styleSheet = document.createStyleSheet();
			styleSheet.cssText = css;
			return styleSheet.owningElement;
		}
	}
});
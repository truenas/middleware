define(["dojo/has", "xstyle/css!../css/has-transforms3d.css"],
function(has){
	// This module defines feature tests for CSS3 features such as transitions.
	// The css-transitions, css-transforms, and css-transforms3d has-features
	// can report either boolean or string:
	// * false indicates no transition support
	// * true indicates prefix-less transition support
	// * string indicates the vendor prefix under which transitions are
	//   supported on the platform

	var cssPrefixes = ["ms", "O", "Moz", "Webkit"],
		testDiv = document.createElement("div");
	
	has.add("css-transitions", function(){
		var style = testDiv.style,
			i;
		
		if(style.transitionProperty !== undefined){ // standard, no vendor prefix
			return true;
		}
		for (i = cssPrefixes.length; i--;) {
			if (style[cssPrefixes[i] + "TransitionProperty"] !== undefined) {
				return cssPrefixes[i]; // vendor-specific css property prefix
			}
		}
		
		return false; // otherwise, not supported
	});
	
	has.add("transitionend", function(){
		// infers transitionend event name based on CSS transitions has-feature
		var tpfx = has("css-transitions");
		if(!tpfx){ return false; }
		if(tpfx === true){ return "transitionend"; }
		return {
			ms: "MSTransitionEnd",
			O: "oTransitionEnd",
			Moz: "transitionend",
			Webkit: "webkitTransitionEnd"
		}[tpfx];
	});
	
	has.add("css-transforms", function(){
		var style = testDiv.style, i;
		if (style.transformProperty !== undefined) {
			return true; // standard, no vendor prefix
		}
		for (i = cssPrefixes.length; i--;) {
			if (style[cssPrefixes[i] + "Transform"] !== undefined) {
				return cssPrefixes[i];
			}
		}
		
		return false; // otherwise, not supported
	});
	
	has.add("css-transforms3d", function(){
		var style = testDiv.style, left, prefix;
		
		// apply csstransforms3d class to test transform-3d media queries
		testDiv.className = "csstransforms3d";
		// add to body to allow measurement
		document.body.appendChild(testDiv);
		left = testDiv.offsetLeft;
		
		if (left === 9) {
			return true; // standard, no prefix
		} else if (left > 9){
			// Matched one of the vendor prefixes; offset indicates which
			prefix = cssPrefixes[left - 10];
			return prefix || false;
		}
		document.body.removeChild(testDiv);
		
		return false; // otherwise, not supported
	});
	
	return has;
});

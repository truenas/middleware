define(["put-selector/put"], function(put){
	// summary:
	//		This module defines miscellaneous utility methods for purposes of
	//		adding styles, and throttling/debouncing function calls.
	
	// establish an extra stylesheet which addCssRule calls will use,
	// plus an array to track actual indices in stylesheet for removal
	var extraRules = [],
		extraSheet,
		removeMethod,
		rulesProperty,
		invalidCssChars = /([^A-Za-z0-9_\u00A0-\uFFFF-])/g;
	
	function removeRule(index){
		// Function called by the remove method on objects returned by addCssRule.
		var realIndex = extraRules[index],
			i, l;
		if (realIndex === undefined) { return; } // already removed
		
		// remove rule indicated in internal array at index
		extraSheet[removeMethod](realIndex);
		
		// Clear internal array item representing rule that was just deleted.
		// NOTE: we do NOT splice, since the point of this array is specifically
		// to negotiate the splicing that occurs in the stylesheet itself!
		extraRules[index] = undefined;
		
		// Then update array items as necessary to downshift remaining rule indices.
		// Can start at index + 1, since array is sparse but strictly increasing.
		for(i = index + 1, l = extraRules.length; i < l; i++){
			if(extraRules[i] > realIndex){ extraRules[i]--; }
		}
	}
	
	var util = {
		// Throttle/debounce functions
		
		defaultDelay: 15,
		throttle: function(cb, context, delay){
			// summary:
			//		Returns a function which calls the given callback at most once per
			//		delay milliseconds.  (Inspired by plugd)
			var ran = false;
			delay = delay || util.defaultDelay;
			return function(){
				if(ran){ return; }
				ran = true;
				cb.apply(context, arguments);
				setTimeout(function(){ ran = false; }, delay);
			};
		},
		throttleDelayed: function(cb, context, delay){
			// summary:
			//		Like throttle, except that the callback runs after the delay,
			//		rather than before it.
			var ran = false;
			delay = delay || util.defaultDelay;
			return function(){
				if(ran){ return; }
				ran = true;
				var a = arguments;
				setTimeout(function(){
					ran = false;
					cb.apply(context, a);
				}, delay);
			};
		},
		debounce: function(cb, context, delay){
			// summary:
			//		Returns a function which calls the given callback only after a
			//		certain time has passed without successive calls.  (Inspired by plugd)
			var timer;
			delay = delay || util.defaultDelay;
			return function(){
				if(timer){
					clearTimeout(timer);
					timer = null;
				}
				var a = arguments;
				timer = setTimeout(function(){
					cb.apply(context, a);
				}, delay);
			};
		},
		
		// Iterative functions
		
		each: function(arrayOrObject, callback, context){
			// summary:
			//		Given an array or object, iterates through its keys.
			//		Does not use hasOwnProperty (since even Dojo does not
			//		consistently use it), but will iterate using a for or for-in
			//		loop as appropriate.
			
			var i, len;
			
			if(!arrayOrObject){
				return;
			}
			
			if(typeof arrayOrObject.length === "number"){
				for(i = 0, len = arrayOrObject.length; i < len; i++){
					callback.call(context, arrayOrObject[i], i, arrayOrObject);
				}
			}else{
				for(i in arrayOrObject){
					callback.call(context, arrayOrObject[i], i, arrayOrObject);
				}
			}
		},
		
		// CSS-related functions
		
		addCssRule: function(selector, css){
			// summary:
			//		Dynamically adds a style rule to the document.  Returns an object
			//		with a remove method which can be called to later remove the rule.
			
			if(!extraSheet){
				// First time, create an extra stylesheet for adding rules
				extraSheet = put(document.getElementsByTagName("head")[0], "style");
				// Keep reference to actual StyleSheet object (`styleSheet` for IE < 9)
				extraSheet = extraSheet.sheet || extraSheet.styleSheet;
				// Store name of method used to remove rules (`removeRule` for IE < 9)
				removeMethod = extraSheet.deleteRule ? "deleteRule" : "removeRule";
				// Store name of property used to access rules (`rules` for IE < 9)
				rulesProperty = extraSheet.cssRules ? "cssRules" : "rules";
			}
			
			var index = extraRules.length;
			extraRules[index] = (extraSheet.cssRules || extraSheet.rules).length;
			extraSheet.addRule ?
				extraSheet.addRule(selector, css) :
				extraSheet.insertRule(selector + '{' + css + '}', extraRules[index]);
			
			return {
				get: function(prop) {
					return extraSheet[rulesProperty][extraRules[index]].style[prop];
				},
				set: function(prop, value) {
					if (typeof extraRules[index] !== "undefined") {
						extraSheet[rulesProperty][extraRules[index]].style[prop] = value;
					}
				},
				remove: function(){
					removeRule(index);
				}
			};
		},
		
		escapeCssIdentifier: function(id){
			// summary:
			//		Escapes normally-invalid characters in a CSS identifier (such as .);
			//		see http://www.w3.org/TR/CSS2/syndata.html#value-def-identifier
			// id: String
			//		CSS identifier (e.g. tag name, class, or id) to be escaped
			
			return id.replace(invalidCssChars, "\\$1");
		}
	};
	return util;
});
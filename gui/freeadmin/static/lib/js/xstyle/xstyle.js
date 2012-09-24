if(typeof define == "undefined"){
	(function(){
		// pseudo passive loader
		var modules = {};
		define = function(id, deps, factory){
			for(var i = 0;i < deps.length; i++){
				deps[i] = modules[deps[i]];
			}
			modules[id] = factory.apply(this, deps);
		};
		require = function(deps){
			define("", deps, factory);
		};
	})();
}
define("xstyle/xstyle", ["require"], function (require) {
	"use strict";
	var undef, testDiv = document.createElement("div");
	function search(tag){
		var elements = document.getElementsByTagName(tag);
		for(var i = 0; i < elements.length; i++){
			checkImports(elements[i]);
		}
	}
	var ua = navigator.userAgent;
	var vendorPrefix = ua.indexOf("WebKit") > -1 ? "-webkit-" :
		ua.indexOf("Firefox") > -1 ? "-moz-" :
		ua.indexOf("MSIE") > -1 ? "-ms-" :
		ua.indexOf("Opera") > -1 ? "-o-" : "";
	function checkImports(element, callback, fixedImports){
		var sheet = element.sheet || element.styleSheet;
		var needsParsing = sheet.needsParsing, // load-imports can check for the need to parse when it does it's recursive look at imports 
			cssRules = sheet.rules || sheet.cssRules;
		function fixImports(){
			// need to fix imports, applying load-once semantics for all browsers, and flattening for IE to fix nested @import bugs
			require(["./load-imports"], function(load){
				load(element, function(){
					checkImports(element, callback, true);
				});
			});
		}
		if(sheet.imports && !fixedImports && sheet.imports.length){
			// this is how we check for imports in IE
			return fixImports();
		}
		if(!needsParsing){
			for(var i = 0; i < cssRules.length; i++){								
				var rule = cssRules[i];
				if(rule.href && !fixedImports){
					// it's an import (for non-IE browsers)
					return fixImports();
				}
				if(rule.selectorText && rule.selectorText.substring(0,2) == "x-"){
					// an extension is used, needs to be parsed
					needsParsing = true;
				}
			}
		}
		if(needsParsing){
			// ok, determined that CSS extensions are in the CSS, need to get the source and really parse it
			parse(sheet.source || sheet.ownerElement.innerHTML, sheet, callback);
		}
	}
	function parse(css, styleSheet, callback) {
		// normalize the stylesheet.
		if(!styleSheet.addRule){
			// only FF doesn't have this
			styleSheet.addRule = function(selector, style, index){
				return this.insertRule(selector + "{" + style + "}", index >= 0 ? index : this.cssRules.length);
			}
		}
		if(!styleSheet.deleteRule){
			styleSheet.deleteRule = sheet.removeRule;
		}
		var handlers = {property:{}};
		function addHandler(type, name, module){
			var handlersForType = handlers[type] || (handlers[type] = {});
			handlersForType[name] = module;
		}
		function addExtensionHandler(type){
			if(!handlers[type]){
				handlers[type] = {};
			}
			addHandler("selector", 'x-' + type, {
				onRule: function(rule){
					rule.eachProperty(function(name, value){
						do{
							var parts = value.match(/require\s*\((.+)\)|([^, ]+)([, ]+(.+))?/);
							if(parts[1]){
								return addHandler(type, name, parts[1]);
							}
							var first = parts[2];
							if(first == "default"){
								if((type == "property" && typeof testDiv.style[name] == "string")){
									return;
								}
								if(type == "pseudo"){
									try{
										document.querySelectorAll("x:" + name);
										return;
									}catch(e){}
								}
							}else if(first == "prefix"){
								if(typeof testDiv.style[vendorPrefix + name] == "string"){
									return addHandler(type, name, 'xstyle/xstyle');
								}
							}else{
								return addHandler(type, name, function(){
									return value;
								});
							}
						}while(value = parts[4]);
/*						var ifUnsupported = value.charAt(value.length - 1) == "?";
						value = value.replace(/require\s*\(|\)\??/g, '');
						if(!ifUnsupported || typeof testDiv.style[name] != "string"){ // if conditioned on support, test to see browser has that style
							// not supported as a standard property, now let's check to see if we can support it with vendor prefixing
							if(ifUnsupported && typeof testDiv.style[vendorPrefix + name] == "string"){
								// it does support vendor prefixing, fix it with that
								value = 'xstyle/xstyle';
							}
							addHandler(type, name, value);
						}*/
					});
				}
			});
		}
		addExtensionHandler("property");
		addExtensionHandler("value");
		addExtensionHandler("pseudo");
		var waiting = 1;
		var baseUrl = (styleSheet.href || location.href).replace(/[^\/]+$/,'');
		var properties = [], values = [];
		var valueModules = {};
		
		var convertedRules = [];
		var valueRegex = new RegExp("(?:^|\\W)(" + values.join("|") + ")(?:$|\\W)");
		function Rule () {}
		Rule.prototype = {
			eachProperty: function (onproperty, propertyRegex) {
				var selector, css;
				selector = this.selector; //(this.children ? onproperty(0, "layout", this.children) || this.selector : this.selector);
				this.cssText.replace(/\s*([^;:]+)\s*:\s*([^;]+)?/g, function (full, name, value) {
					onproperty(name, value);
				});
				if(this.children){
					for(var i = 0; i < this.children.length; i++){
						var child = this.children[i];
						if(!child.selector){ // it won't have a selector if it is property with nested properties
							onproperty(child.property, child);
						}
					}
				}
			},
			fullSelector: function(){
				return (this.parent ? this.parent.fullSelector() : "") + (this.selector || "") + " ";  
			},
			add: function(selector, cssText){
				if(cssText){
					styleSheet.addRule ?
						styleSheet.addRule(selector, cssText) :
						styleSheet.insertRule(selector + '{' + cssText + '}', styleSheet.cssRules.length);
				}
			},
			cssText: ""
		};
		
		var lastRule = new Rule;
		lastRule.css = css;
		
		function onProperty(name, value) {
			// this is called for each CSS property
			var propertyName = name;
			do{
				var handlerForName = handlers.property[name];
				if(handlerForName){
					return handler(handlerForName, "onProperty", propertyName, value);
				}
				// if we didn't match, we try to match property groups, for example "background-image" should match the "background" listener 
				name = name.substring(0, name.lastIndexOf("-"));
			}while(name);
		}
		function onIdentifier(identifier, name, value){
			var handlerForName = handlers.value[identifier];
			if(handlerForName){
				handler(handlerForName, "onIdentifier", name, value);
			}
		}
		function onRule(selector, rule){
			var handlerForName = handlers.selector[selector];
			if(handlerForName){
				handler(handlerForName, "onRule", rule);
			}
		}
		function onPseudo(pseudo, rule){
			var handlerForName = handlers.pseudo[pseudo];
			if(handlerForName){
				handler(handlerForName, "onPseudo", pseudo, rule);
			}
		}
		function handler(module, type, name, value){
			if(module){
				var rule = lastRule;
				var ruleHandled = function(text){
					console.log("loaded ", module, text);
					if(text){
						/* TODO: is the a way to determine the index deterministically?
						var cssRules = styleSheet.rules || styleSheet.cssRules;
						for(var index = rule.index || 0; index < cssRules.length; index++){
							if(cssRules[index].selectorText == rule.fullSelector(){
								break;
							}
						}*/
						/* TODO: merge IE filters
						if(isIE){
							var filters = [];
							convertedText = convertedText.replace(/filter: ([^;]+);/g, function(t, filter){
								filters.push(filter);
								return "";
							});
							if(filters.length){
								console.log("filters", filters);
								convertedText = "zoom: 1;filter: " + filters.join("") + ";" + convertedText;
							}
						}
						*/
						styleSheet.addRule(rule.fullSelector(), text);
					}
					finishedLoad();
				};
				
				waiting++;
				console.log("loading ", module, name, value);
				var onLoad = function(module){
					var result = module[type](name, value, rule, styleSheet);
					if(result && result.then){
							// a promise, return immediately defer handling
						result.then(ruleHandled);
					}else{
						ruleHandled(result);
					}
				}
				typeof module == "string" ? require([module], onLoad) : onLoad(module);					
			}
		}
		// parse the CSS, finding each rule
		css.replace(/\s*(?:([^{;\s]+)\s*{)?\s*([^{}]+;)?\s*(};?)?/g, function (full, selector, properties, close) {
			// called for each rule
			if (selector) {
				// a selector was found, start a new rule (note this can be nested inside another selector)
				var newRule = new Rule();
				(lastRule.children || (lastRule.children = [])).push(newRule); // add to the parent layout 
				newRule.parent = lastRule;
				if(selector.charAt(selector.length - 1) == ":"){
					// it is property style nesting
					newRule.property= selector.substring(0, selector.length - 1);
				}else{
					// just this segment of selector
					newRule.selector = selector; 
				}
				lastRule = newRule;
			}
			if (properties) {
				// some properties were found
				lastRule.cssText += properties;
			}
			if (close) {
				// rule was closed with }
				// TODO: use a specialized regex that only looks for registered properties
				lastRule.cssText.replace(/\s*([^;:]+)\s*:\s*([^;]+)?/g, function (full, name, value) {
					onProperty(name, value);
					value.replace(valueRegex, function(t, identifier){
						//onIdentifier(identifier, name, value);
					});
				});
				if(lastRule.children){
					for(var i = 0; i < lastRule.children.length; i++){
						var child = lastRule.children[i];
						if(!child.selector){ // it won't have a selector if it is property with nested properties
							onProperty(child.property, child);
						}
					}
				}
				onRule(lastRule.selector, lastRule);
				lastRule.selector && lastRule.selector.replace(/:([-\w]+)/, function(t, pseudo){
					return onPseudo(pseudo, lastRule);
				});
				lastRule = lastRule.parent;
			}
		});
		function finishedLoad(){
			if(--waiting == 0){
				if(callback){
					callback(styleSheet);
				}
			}
		}		
		finishedLoad();
	}
	search('link');
	search('style');
	var xstyle =  {
		process: checkImports,
		vendorPrefix: vendorPrefix,
		onProperty: function(name, value){
			// basically a noop for most operations, we rely on the vendor prefixing in the main property parser 
			if(name == "opacity" && vendorPrefix == "-ms-"){
				return 'filter: alpha(opacity=' + (value * 100) + '); zoom: 1;';
			}
			return vendorPrefix + name + ':' + value + ';';
		}
	};
	return xstyle;

});

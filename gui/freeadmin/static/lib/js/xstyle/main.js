define("xstyle/main", ["require", "xstyle/core/parser", "xstyle/core/base", "xstyle/core/elemental"], function (require, parser, ruleModel, elemental) {
	"use strict";
	function search(tag){
		// used to search for link and style tags
		var elements = document.getElementsByTagName(tag);
		for(var i = 0; i < elements.length; i++){
			checkImports(elements[i]);
		}
	}
	elemental.ready(function(){
		// search the document for <link> and <style> elements to potentially parse.
		search('link');
		search('style');
	});
	// traverse the @imports to load the sources 
	function checkImports(element, callback, fixedImports){
		var sheet = element.sheet || element.styleSheet || element;
		var needsParsing = sheet.needsParsing, // load-imports can check for the need to parse when it does it's recursive look at imports 
			cssRules = sheet.rules || sheet.cssRules;
		function fixImports(){
			// need to fix imports, applying load-once semantics for all browsers, and flattening for IE to fix nested @import bugs
			require(["xstyle/core/load-imports"], function(load){
				load(element, function(){
					checkImports(element, callback, true);
				});
			});
		}
		function checkForInlinedExtensions(sheet){
			var cssRules = sheet.cssRules;
			for(var i = 0; i < cssRules.length; i++){								
				var rule = cssRules[i];
				if(rule.selectorText && rule.selectorText.substring(0,2) == "x-"){
					// an extension is used, needs to be parsed
					needsParsing = true;
					if(/^'/.test(rule.style.content)){
						// this means we are in a built sheet, and can directly parse it
						parse(eval(rule.style.content), sheet, callback);
						return true;
					}
				}
			}
		}
		if((sheet.href || (sheet.imports && sheet.imports.length)) && !fixedImports){
			// this is how we check for imports in IE
			return fixImports();
		}
		if(!needsParsing){
			for(var i = 0; i < cssRules.length; i++){								
				var rule = cssRules[i];
				if(rule.href && !fixedImports){
					// it's an import (for non-IE browsers)
					if(!checkForInlinedExtensions(rule.styleSheet)){
						return fixImports();
					}
					return;
				}
			}
		}
		// ok, determined that CSS extensions are in the CSS, need to get the source and really parse it
		parse(sheet.localSource || (sheet.ownerNode || sheet.owningElement).innerHTML, sheet, callback);
	}
	parser.getStyleSheet = function(importRule, sequence){
		return importRule.styleSheet || importRule;
	};
	function parse(textToParse, styleSheet, callback) {
		// this function is responsible for parsing a stylesheet with all of xstyle's syntax rules
		
		// normalize the stylesheet.
		if(!styleSheet.addRule){
			// only FF doesn't have this
			styleSheet.addRule = function(selector, style, index){
				return this.insertRule(selector + "{" + style + "}", index >= 0 ? index : this.cssRules.length);
			}
		}
		if(!styleSheet.deleteRule){
			styleSheet.deleteRule = styleSheet.removeRule;
		}
	

		var waiting = 1;
		// determine base url
		var baseUrl = (styleSheet.href || location.href).replace(/[^\/]+$/,'');

		// keep references
		ruleModel.css = textToParse;		
		
		// call the parser
		parser(ruleModel, textToParse, styleSheet);
		
		function finishedLoad(){
			// this is called after each asynchronous action is completed, allowing us to determine
			// when everything is complete
			if(--waiting == 0){
				if(callback){
					callback(styleSheet);
				}
			}
		}
		// synchronous completion
		finishedLoad(ruleModel);
		return ruleModel;
	}
	
	var xstyle =  {
		process: checkImports,
		parse: parse,
		
		load:  function(resourceDef, require, callback, config){
			// support use an AMD plugin loader
			require(['xstyle/css'], function(plugin){
				plugin.load(resourceDef, require, callback, config);
			});
		}
	};
	return xstyle;

});

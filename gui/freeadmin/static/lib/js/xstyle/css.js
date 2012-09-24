define(["require"], function(moduleRequire){
"use strict";
var cssCache = window.cssCache || (window.cssCache = {});
/*
 * RequireJS css! plugin
 * This plugin will load and wait for css files.  This could be handy when
 * loading css files as part of a layer or as a way to apply a run-time theme. This
 * module checks to see if the CSS is already loaded before incurring the cost
 * of loading the full CSS loader codebase
 */
/* 	function search(tag, href){
		var elements = document.getElementsByTagName(tag);
		for(var i = 0; i < elements.length; i++){
			var element = elements[i];
			var sheet = alreadyLoaded(element.sheet || element.styleSheet, href)
			if(sheet){
				return sheet;
			}
		}
	}
	function alreadyLoaded(sheet, href){
		if(sheet){
			var importRules = sheet.imports || sheet.rules || sheet.cssRules;
			for(var i = 0; i < importRules.length; i++){								
				var importRule = importRules[i];
				if(importRule.href){
					sheet = importRule.styleSheet || importRule;
					if(importRule.href == href){
						return sheet;
					}
					sheet = alreadyLoaded(sheet, href);
					if(sheet){
						return sheet;
					}
				}
			}
		}
	}
	function nameWithExt (name, defaultExt) {
		return name.lastIndexOf('.') <= name.lastIndexOf('/') ?
			name + '.' + defaultExt : name;
	}*/
 	return {
		load: function (resourceDef, require, callback, config) {
			var url = require.toUrl(resourceDef);
			if(cssCache[url]){
				return createStyleSheet(cssCache[url]);
			}
/*			var cssIdTest = resourceDef.match(/(.+)\?(.+)/);
			if(cssIdTest){*/
				// if there is an id test available, see if the referenced rule is already loaded,
				// and if so we can completely avoid any dynamic CSS loading. If it is
				// not present, we need to use the dynamic CSS loader.
				var docElement = document.documentElement;
				var testDiv = docElement.insertBefore(document.createElement('div'), docElement.firstChild);
				testDiv.id = require.toAbsMid(resourceDef).replace(/\//g,'-').replace(/\..*/,'') + "-loaded";  //cssIdTest[2];
				var displayStyle = (testDiv.currentStyle || getComputedStyle(testDiv, null)).display;
				docElement.removeChild(testDiv);
				if(displayStyle == "none"){
					return callback();
				}
				//resourceDef = cssIdTest[1];
			//}
			// use dynamic loader
			/*if(search("link", url) || search("style", url)){
				callback();
			}else{*/
			moduleRequire(["./load-css"], function(load){
				load(url, callback);
			});
		},
		pluginBuilder: "xstyle/css-builder"

	};
});

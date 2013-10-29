define(["require"], function(moduleRequire){
"use strict";
/*
 * AMD css! plugin
 * This plugin will load and wait for css files.  This could be handy when
 * loading css files as part of a layer or as a way to apply a run-time theme. This
 * module checks to see if the CSS is already loaded before incurring the cost
 * of loading the full CSS loader codebase
 */
 	function testElementStyle(tag, id, property){
 		// test an element's style
		var docElement = document.documentElement;
		var testDiv = docElement.insertBefore(document.createElement(tag), docElement.firstChild);
		testDiv.id = id;
		var styleValue = (testDiv.currentStyle || getComputedStyle(testDiv, null))[property];
		docElement.removeChild(testDiv);
 		return styleValue;
 	} 
 	return {
		load: function(resourceDef, require, callback, config) {
			var url = require.toUrl(resourceDef);
			var cachedCss = require.cache && require.cache['url:' + url];
			if(cachedCss){
				// we have CSS cached inline in the build
				if(cachedCss.xCss){
					var parser = cachedCss.parser;
					var xCss =cachedCss.xCss;
					cachedCss = cachedCss.cssText;
				}
				moduleRequire(['./util/createStyleSheet'],function(createStyleSheet){
					createStyleSheet(cachedCss);
				});
				if(xCss){
					//require([parsed], callback);
				}
				return checkForParser();
			}
			function checkForParser(){
				var parser = testElementStyle('x-parse', null, 'content');
				if(parser && parser != 'none'){
					// TODO: wait for parser to load
					require([eval(parser)], callback);
				}else{
					callback();
				}
			}
			
			// if there is an id test available, see if the referenced rule is already loaded,
			// and if so we can completely avoid any dynamic CSS loading. If it is
			// not present, we need to use the dynamic CSS loader.
			var displayStyle = testElementStyle('div', resourceDef.replace(/\//g,'-').replace(/\..*/,'') + "-loaded", 'display');
			if(displayStyle == "none"){
				return checkForParser();
			}
			// use dynamic loader
			moduleRequire(["./core/load-css"], function(load){
				load(url, checkForParser);
			});
		}
	};
});

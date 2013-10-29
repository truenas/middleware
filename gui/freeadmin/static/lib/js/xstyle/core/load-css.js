/**
 * This includes code from https://github.com/unscriptable/cssx
 * Copyright (c) 2010 unscriptable.com
 */

/*jslint browser:true, on:true, sub:true */

define([], function(){
"use strict";

/*
 * AMD css! plugin
 * This plugin will load and wait for css files.  This could be handy when
 * loading css files as part of a layer or as a way to apply a run-time theme.
 * Most browsers do not support the load event handler of the link element.
 * Therefore, we have to use other means to detect when a css file loads.
 * (The HTML5 spec states that the LINK element should have a load event, but
 * not even Chrome 8 or FF4b7 have it, yet.
 * http://www.w3.org/TR/html5/semantics.html#the-link-element)
 *
 * This plugin tries to use the load event and a universal work-around when
 * it is invoked the first time.  If the load event works, it is used on
 * every successive load.  Therefore, browsers that support the load event will
 * just work (i.e. no need for hacks!).  FYI, Feature-detecting the load
 * event is tricky since most browsers have a non-functional onload property.
 *
 * The universal work-around watches a stylesheet until its rules are
 * available (not null or undefined).  There are nuances, of course, between
 * the various browsers.  The isLinkReady function accounts for these.
 *
 * Note: it appears that all browsers load @import'ed stylesheets before
 * fully processing the rest of the importing stylesheet. Therefore, we
 * don't need to find and wait for any @import rules explicitly.
 *
 * Note #2: for Opera compatibility, stylesheets must have at least one rule.
 * AFAIK, there's no way to tell the difference between an empty sheet and
 * one that isn't finished loading in Opera (XD or same-domain).
 *
 * Options:
 *      !nowait - does not wait for the stylesheet to be parsed, just loads it
 *
 * Global configuration options:
 *
 * cssDeferLoad: Boolean. You can also instruct this plugin to not wait
 * for css resources. They'll get loaded asap, but other code won't wait
 * for them. This is just like using the !nowait option on every css file.
 *
 * cssWatchPeriod: if direct load-detection techniques fail, this option
 * determines the msec to wait between brute-force checks for rules. The
 * default is 50 msec.
 *
 * You may specify an alternate file extension:
 *      require('css!myproj/component.less') // --> myproj/component.less
 *      require('css!myproj/component.scss') // --> myproj/component.scss
 *
 * When using alternative file extensions, be sure to serve the files from
 * the server with the correct mime type (text/css) or some browsers won't
 * parse them, causing an error in the plugin.
 *
 * usage:
 *      require(['css!myproj/comp']); // load and wait for myproj/comp.css
 *      define(['css!some/folder/file'], {}); // wait for some/folder/file.css
 *      require(['css!myWidget!nowait']);
 *
 * Tested in:
 *      Firefox 1.5, 2.0, 3.0, 3.5, 3.6, and 4.0b6
 *      Safari 3.0.4, 3.2.1, 5.0
 *      Chrome 7 (8+ is partly b0rked)
 *      Opera 9.52, 10.63, and Opera 11.00
 *      IE 6, 7, and 8
 *      Netscape 7.2 (WTF? SRSLY!)
 * Does not work in Safari 2.x :(
 * In Chrome 8+, there's no way to wait for cross-domain (XD) stylesheets.
 * See comments in the code below.
 * TODO: figure out how to be forward-compatible when browsers support HTML5's
 *  load handler without breaking IE and Opera
*/


	var
		// compressibility shortcuts
		onreadystatechange = 'onreadystatechange',
		onload = 'onload',
		createElement = 'createElement',
		// failed is true if RequireJS threw an exception
		failed = false,
		doc = document,
		cache = typeof _css_cache == "undefined" ? {} : _css_cache,
		undef,
		features = {
			"event-link-onload": document.createElement("link").onload === null &&
				// safari lies about the onload event
				!navigator.userAgent.match(/AppleWebKit/),
			"dom-create-style-element": !document.createStyleSheet
		},
		// find the head element and set it to it's standard property if nec.
		head = doc.head || (doc.head = doc.getElementsByTagName('head')[0]);

	function has (feature) {
		return features[feature];
	}
	function createLink (doc, optHref) {
		var link = doc[createElement]('link');
		link.rel = "stylesheet";
		link.type = "text/css";
		if (optHref) {
			link.href = optHref;
		}
		return link;
	}
	function nameWithExt (name, defaultExt) {
		return name.lastIndexOf('.') <= name.lastIndexOf('/') ?
			name + '.' + defaultExt : name;
	}
	function parseSuffixes (name) {
		// creates a dual-structure: both an array and a hashmap
		// suffixes[0] is the actual name
		var parts = name.split('!'),
			suf, i = 1, pair;
		while ((suf = parts[i++])) { // double-parens to avoid jslint griping
			pair = suf.split('=', 2);
			parts[pair[0]] = pair.length == 2 ? pair[1] : true;
		}
		return parts;
	}
		

	if(!has("bundled-css")){ // if all the CSS is bundled, we don't need to the loader code
		var loadDetector = function(params, cb){ 
			// failure detection
			// we need to watch for onError when using RequireJS so we can shut off
			// our setTimeouts when it encounters an error.
			if (require.onError) {
				require.onError = (function (orig) {
					return function () {
						failed = true;
						orig.apply(this, arguments);
					}
				})(require.onError);
			}
		
			/***** load-detection functions *****/
		
			function loadHandler (params, cb) {
				// We're using 'readystatechange' because IE and Opera happily support both
				var link = params.link;
				link[onreadystatechange] = link[onload] = function () {
					if (!link.readyState || link.readyState == 'complete') {
						features["event-link-onload"] = true;
						cleanup(params);
						cb();
					}
				};
			}
		
		
			function isLinkReady (link) {
				// based on http://www.yearofmoo.com/2011/03/cross-browser-stylesheet-preloading.html
				// Therefore, we need
				// to continually test beta browsers until they all support the LINK load
				// event like IE and Opera.
				// webkit's and IE's sheet is null until the sheet is loaded
				var sheet = link.sheet || link.styleSheet;
				if(sheet){
					var styleSheets = document.styleSheets;
					for(var i = styleSheets.length; i > 0; i--){
						if(styleSheets[i-1] == sheet){
							return true;
						}
					}
				}
			}
		
			function ssWatcher (params, cb) {
				// watches a stylesheet for loading signs.
				if (isLinkReady(params.link)) {
					cleanup(params);
					cb();
				}
				else if (!failed) {
					setTimeout(function () { ssWatcher(params, cb); }, params.wait);
				}
			}
		
			function cleanup (params) {
				var link = params.link;
				link[onreadystatechange] = link[onload] = null;
			}
			// It would be nice to use onload everywhere, but the onload handler
			// only works in IE and Opera.
			// Detecting it cross-browser is completely impossible, too, since
			// THE BROWSERS ARE LIARS! DON'T TELL ME YOU HAVE AN ONLOAD PROPERTY
			// IF IT DOESN'T DO ANYTHING!
			var loaded;
			function cbOnce () {
				if (!loaded) {
					loaded = true;
					cb();
				}
			}
			loadHandler(params, cbOnce);
			if (!has("event-link-onload")) ssWatcher(params, cbOnce);
		
		};
	}
	function insertCss(css){
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
	/***** finally! the actual plugin *****/
	return function (resourceDef, callback, config) {
				var resources = resourceDef.split(","),
					loadingCount = resources.length,

				// all detector functions must ensure that this function only gets
				// called once per stylesheet!
					loaded = 
				function () {
					// load/error handler may have executed before stylesheet is
					// fully parsed / processed in Opera, so use setTimeout.
					// Opera will process before the it next enters the event loop
					// (so 0 msec is enough time).
					if(--loadingCount == 0){
						// TODO: move this setTimeout to loadHandler
						callback(link.sheet || link.styleSheet)
						// TODO: Is this need for Opera?
						//setTimeout(onCssLoaded,0);
					}
				}

				// after will become truthy once the loop executes a second time
				for(var i = 0, after; i < resources.length; i++, after = url){
					resourceDef = resources[i];
					var cached = cache[resourceDef]; 
					if(cached){
						link = insertCss(cached);
						return loaded();
					}
					var
						// TODO: this is a bit weird: find a better way to extract name?
						opts = parseSuffixes(resourceDef),
						name = opts.shift(),
						url = nameWithExt(name, "css"),
						link = createLink(doc),
						nowait = 'nowait' in opts ? opts.nowait != 'false' : !!(config && config.cssDeferLoad),
						params = {
							link: link,
							url: url,
							wait: config && config.cssWatchPeriod || 25
						};
					// hook up load detector(s)
					loadDetector(params, loaded);
					if (nowait) {
						callback(link);
					}

					// go!
					link.href = url;

					head.appendChild(link);
				}
			};

});

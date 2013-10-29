// summary:
//		This script scans for stylesheets and flattens imports in IE (to fix the deep import bug),
//		and provides loading of the text of any sheets. This is intended to only be loaded as needed
// 		for development, ideally stylesheets should be flattened and inlined for finished/production
// 		applications, and this module won't be loaded.  
define('xstyle/core/load-imports', [], function(){
	var insertedSheets = {},
		features = {
			"dom-deep-import": !document.createStyleSheet // essentially test to see if it is IE, inaccurate marker, maybe should use dom-addeventlistener? 
		};
	function has (feature) {
		return features[feature];
	}
	// load any plugin modules when done parsing
	function load(link, callback){
		var sheet = link.sheet || link.styleSheet;
		
		loadingCount = 1;
		
		function finishedModule(){
			if(!--loadingCount){
				aggregateSource(sheet);
				callback && callback(sheet);
			}
		}
		function aggregateSource(sheet){
			var source = "";
			var importRules = !sheet.disabled && (sheet.imports || sheet.rules || sheet.cssRules);
			
			for(var i = 0; i < importRules.length; i++){										
				var rule = importRules[i];
				if(rule.href){
					source += aggregateSource(rule.styleSheet || rule);
				}
			}
			return sheet.source = source + sheet.localSource;
		}
		if(false && !has("dom-deep-import")){
			// in IE, so we flatten the imports due to IE's lack of support for deeply nested @imports
			// and fix the computation of URLs (IE calculates them wrong)
			var computeImportUrls = function(sheet, baseUrl){
				var computedUrls = []
				// IE miscalculates .href properties, so we calculate them by parsing
				sheet.cssText.replace(/@import url\( ([^ ]+) \)/g, function(t, url){
						// we have to actually parse the cssText because IE's href property is totally wrong
						computedUrls.push(absoluteUrl(baseUrl, url));
					});
				return computedUrls;
			},
			flattenImports = function(){
				// IE doesn't support deeply nested @imports, so we flatten them.
				//	IE needs imports rearranged and then to go through on a later turn.
				// This function is a big pile of IE fixes
				var flatteningOccurred, sheet = link.styleSheet;
				if(sheet.processed){
					return;
				}
				var sheetHref = sheet.correctHref = absoluteUrl(location.toString(), sheet.href);
				if(!sheet.computedUrls){
					// we have to do in a pre-loop or else IE's messes up on it's ownerRule's order
					sheet.computedUrls = computeImportUrls(sheet, sheetHref);
				}
				for(var i = 0; i < sheet.imports.length; i++){
					var importedSheet = sheet.imports[i];
					if(!importedSheet.cssText && !importedSheet.imports.length){ // empty means it is not loaded yet, try again later
						setTimeout(flattenImports, 50);
						return;
					}
				//	importedSheet.loaded = true;
					var correctHref = importedSheet.correctHref = sheet.computedUrls[i];
					
					var childHrefs = computeImportUrls(importedSheet, correctHref);
					// Deep in an IE stylesheet
					for(var j = 0; j < importedSheet.imports.length; j++){
						// TODO: Think we can just stay in place and remove
						var subImport = importedSheet.imports[j];
						if(!subImport.correctHref){
							flatteningOccurred = true;
							link.onload = flattenImports;
							var childHref = childHrefs[j] || importedSheet.href;
							sheet.computedUrls.splice(i, 0, childHref);
							try{
								sheet.addImport(childHref, i++);
							}catch(e){
								// this will fail if there are too many imports
							}
							subImport.correctHref = childHref; 
						}
					}
				}
				if(flatteningOccurred){
					setTimeout(flattenImports, 50);
				}else{
					sheet.processed = true;
					loadOnce(sheet);
				}
			}
			flattenImports();
			return finishedModule();
		}
		
		loadOnce(sheet);
		finishedModule();
		function loadOnce(sheet, baseUrl){
			// This function is responsible for implementing the @import once
			// semantics, such extra @imports that resolve to the same
			// CSS file are eliminated, and only the first one is kept
			
			var href = absoluteUrl(baseUrl, sheet.correctHref || sheet.href);
			// do normalization
			// TODO: remove this normalization, it is done in xstyle 
			if(!sheet.addRule){
				// only FF doesn't have this
				sheet.addRule = function(selector, style, index){
					return this.insertRule(selector + "{" + style + "}", index >= 0 ? index : this.cssRules.length);
				}
			}
			if(!sheet.deleteRule){
				sheet.deleteRule = sheet.removeRule;
			}
			var existingSheet = href && insertedSheets[href]; 
			if(existingSheet){
				var sheetToDelete;
				if(existingSheet != sheet){
					var parentStyleSheet = sheet.parentStyleSheet;
					var existingElement = existingSheet.ownerElement;
					if(existingElement.compareDocumentPosition ? 
							existingElement.compareDocumentPosition(link) != 2 :
							existingElement.sourceIndex <= link.sourceIndex){
						// this new sheet is after (or current), so we kill this one
						sheetToDelete = sheet;
					}else{
						// the other sheet is after, so delete it
						sheetToDelete = existingSheet;
						existingSheet = insertedSheets[href] = sheet;
					}
					// need to delegate to sheet that we are going to preserve
					// TODO: might need to use a queue to store changes and delegate changes that
					// have already taken place on the sheetToDelete
					sheetToDelete.addRule = function(c,s,i){
						existingSheet.addRule(c,s,i > -1 ? i : -1);
					};
					sheetToDelete.deleteRule = function(i){
						existingSheet.deleteRule(i);
					}
					var owner = sheetToDelete.ownerNode || !parentStyleSheet && sheetToDelete.owningElement;
					if(owner){
						// it is top level <link>, remove the node (disabling doesn't work properly in IE, but node removal works everywhere)
						owner.parentNode.removeChild(owner); 
					}else{
						// disabling is the only way to remove an imported stylesheet in firefox; it doesn't work in IE and WebKit
						sheetToDelete.disabled = true; // this works in Opera
						if("cssText" in sheetToDelete){
							sheetToDelete.cssText =""; // this works in IE
						}else{
							// removing the rule is only way to remove an imported stylesheet in WebKit
							owner = sheetToDelete.ownerRule;
							if(owner){
								try{
									var parentStyleSheet = owner.parentStyleSheet;
									var parentRules = parentStyleSheet.cssRules;
									for(var i = 0; i < parentRules.length; i++){
										// find the index of the owner rule that we want to delete
										if(parentRules[i] == owner){
											parentStyleSheet.deleteRule(i);
											break;
										}
									}
									return true;
								}catch(e){
									// opera fails on deleteRule for imports, but the disabled works, so we can continue
									console.log(e);
								}
							}
						}
					}
				}
			}
			if(sheetToDelete != sheet){
				if(href){
					if(/no-xstyle$/.test(href)){
						sheet.localSource = '';
						return;
					}else{
						// record the stylesheet in our hash
						insertedSheets[href] = sheet;
						sheet.ownerElement = link;
						var sourceSheet = sheet;
						loadingCount++;
						fetchText(href, function(text){
							sourceSheet.localSource = text;
							finishedModule();
						}, function(){
							sourceSheet.localSource = '';
							finishedModule();
						});
					}
				}else{
					sheet.localSource = link.innerHTML;
				}
				var cssRules = sheet.rules || sheet.cssRules;
				for(var i = 0; i < cssRules.length; i++){
					var rule = cssRules[i];
					if(rule.selectorText && rule.selectorText.substring(0,2) == "x-"){
						sheet.needsParsing = true;
					}
				}
				
				// now recurse into @import's to check to make sure each of those is only loaded once 
				var importRules = sheet.imports || cssRules;
				
				for(var i = 0; i < importRules.length; i++){										
					var rule = importRules[i];
					if(rule.href){
						// it's an import (for non-IE browsers we are looking at all rules, and need to exclude non-import rules
						var parentStyleSheet = sheet; 
						var childSheet = rule.styleSheet || rule;
						if(loadOnce(childSheet, href)){
							i--; // deleted, so go back in index
						}
						if(childSheet.needsParsing){
							sheet.needsParsing = true;
						}
					}
				}
			}
			// sheetToDelete = null; // Don't entrap IE memory
		}
	}
	function absoluteUrl(base, url) {
		if(!url || url.indexOf(":") > 0 || url.charAt(0) == '/'){
			return url;
		}
		// in IE we do this trick to get the absolute URL
		var lastUrl;
		url = ((base || location.toString()).replace(/[^\/]*$/,'') + url).replace(/\/\.\//g,'/');
		while(lastUrl != url){
			lastUrl = url;
			url = url.replace(/\/[^\/]+\/\.\.\//g, '/');
		}
		return url;
	}
	return load;
	/***** xhr *****/

	var progIds = ['Msxml2.XMLHTTP', 'Microsoft.XMLHTTP', 'Msxml2.XMLHTTP.4.0'];

	function xhr () {
		if (typeof XMLHttpRequest !== "undefined") {
			// rewrite the getXhr method to always return the native implementation
			xhr = function () { return new XMLHttpRequest(); };
		}
		else {
			// keep trying progIds until we find the correct one, then rewrite the getXhr method
			// to always return that one.
			var noXhr = xhr = function () {
					throw new Error("getXhr(): XMLHttpRequest not available");
				};
			while (progIds.length > 0 && xhr === noXhr) (function (id) {
				try {
					new ActiveXObject(id);
					xhr = function () { return new ActiveXObject(id); };
				}
				catch (ex) {}
			}(progIds.shift()));
		}
		return xhr();
	}

	function fetchText (url, callback, errback) {
		var x = xhr();
		x.open('GET', url, true);
		x.onreadystatechange = function (e) {
			if (x.readyState === 4) {
				if (x.status < 400) {
					callback(x.responseText);
				}
				else {
					errback(new Error('fetchText() failed. status: ' + x.statusText));
				}
			}
		};
		x.send(null);
	}
	
});

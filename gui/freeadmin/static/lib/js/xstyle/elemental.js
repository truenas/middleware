/* Provides DOM element level interaction for CSS extensions */
define([], function(){
	var testDiv = document.createElement("div");
	var features = {
		"dom-qsa2.1": !!testDiv.querySelectorAll
	};
	function has(feature){
		return features[feature];
	}
	var matchesSelector = testDiv.matchesSelector || testDiv.webkitMatchesSelector || testDiv.mozMatchesSelector || testDiv.msMatchesSelector || testDiv.oMatchesSelector;
	var selectorRenderers = [];
	var classHash = {}, propertyHash = {};
	var renderQueue = [];
	var documentQueried;
	require(["dojo/domReady!"], function(){
		documentQueried = true;
		if(has("dom-qsa2.1")){
			for(var i = 0, l = selectorRenderers.length; i < l; i++){
				findMatches(selectorRenderers[i]);
			}
			renderWaiting();
		}else{
			var all = document.all;
			for(var i = 0, l = all.length; i < l; i++){
				update(all[i]);
			}
		}
	});//else rely on css expressions (or maybe we should use document.all and just scan everything)
	function findMatches(renderer){
		// find the elements for a given selector and apply the renderers to it
		var toRender = [];
		var results = document.querySelectorAll(renderer.selector);
		var name = renderer.name;
		for(var i = 0, l = results.length; i < l; i++){
			var element = results[i];
			var currentStyle = element.elementalStyle;
			var currentSpecificities = element.elementalSpecificities;
			if(!currentStyle){
				currentStyle = element.elementalStyle = {};
				currentSpecificities = element.elementalSpecificities = {};
			}
			// TODO: only override if the selector is equal or higher specificity
			// var specificity = renderer.selector.match(/ /).length;
			if(true || currentSpecificities[name] <= renderer.specificity){ // only process changes
				var elementRenderings = element.renderings;
				if(!elementRenderings){
					elementRenderings = element.renderings = [];
					renderQueue.push(element);
				}
				
				elementRenderings.push({
					name: name,
					rendered: currentStyle[name] == renderer.propertyValue,
					renderer: renderer
				});
				currentStyle[name] = renderer.propertyValue;
			} 
		}
		
	}
	function renderWaiting(){
		// render all the elements in the queue to be rendered
		for(var i = 0; i < renderQueue.length; i++){
			var element = renderQueue[i];
			var renderings = element.renderings, currentStyle = element.elementalStyle;
			for(var j = 0; j < renderings.length; j++){
				var rendering = renderings[j];
				var renderer = rendering.renderer;
				var rendered = renderer.rendered;
				isCurrent = currentStyle[rendering.name] == renderer.propertyValue; // determine if this renderer matches the current computed style
				if(!rendered && isCurrent){
					renderer.render(element);
				}
				if(rendered && !isCurrent && renderer.unrender){
					renderer.unrender(element);
					renderings.splice(j--, 1); // TODO: need to remove duplicate rendered items as well
				}
			}
		}
		renderQueue = [];
	}
	function apply(element, renderers){
		// an element was found that matches a selector, so we apply the renderers
		for(var i = 0, l = renderers.length; i < l; i++){
			renderers[i](element);
		}
	}
	put = typeof put == "undefined" ? {} : put;
	put.onaddclass = function(element, className){
		var selectorRenderers = classTriggers[className];
		var renderers = selectorRenderers[selector];
		for(var i = 0, l = selectorRenderers.length; i < l; i++){
			var renderer = selectorRenderers[i];
			if(matchesSelector.apply(element, renderer.selector)){
				renderer.render(element);
				(element.renderers = element.renderers || []).push(renderer);
			}
		}
	};
	put.onremoveclass = function(element){
		var elementRenderers = element.renderers;
		if(elementRenderers){
			for(var i = elementRenderers.length - 1; i >= 0; i--){
				var renderer = elementRenderers[i];
				if(!matchesSelector.apply(element, renderer.selector)){
					renderer.unrender(element);
					elementRenderers.splice(i, 1);
				}
			}
		}
	};
	put.oncreateelement = function(element){
		tagTriggers[element.tagName]
	}
	function update(element){
	/* At some point, might want to use getMatchedCSSRules for faster access to matching rules 			
	 	if(typeof getMatchedCSSRules != "undefined"){
			// webkit gives us fast access to which rules apply
			getMatchedCSSRules(element);
		}else{*/
			for(var i = 0, l = selectorRenderers.length; i < l; i++){
			var renderer = selectorRenderers[i];
			if(matchesSelector ?
					// use matchesSelector if available
					matchesSelector.apply(element, renderer.selector) : // TODO: determine if it is higher specificity that other  same name properties
					// else use IE's custom css property inheritance mechanism
					element.currentStyle[renderer.name] == renderer.propertyValue){
				renderer.render(element);
			}
		}
		
	}
	return {
		addRenderer: function(propertyName, propertyValue, rule, handler){
			var renderer = {
				selector: rule.selector,
				propertyValue: propertyValue,
				name: propertyName,
				render: handler
			};
			// the main entry point for adding elemental handlers for a selector. The handler
			// will be called for each element that is created that matches a given selector
			selectorRenderers.push(renderer);
			if(documentQueried){
				findMatches(renderer);
			}
			renderWaiting();
			/*if(!matchesSelector){
				// create a custom property to identify this rule in created elements
				return (renderers.triggerProperty = 'selector_' + encodeURIComponent(selector).replace(/%/g, '/')) + ': 1;' +
					(document.querySelectorAll ? '' : 
						// we use css expressions for IE6-7 to find new elements that match the selector, since qSA is not available, wonder if it is better to just use document.all...
						 'zoom: expression(cssxRegister(this,"' + selector +'"));');
			}*/
		},
		update: update // this should be called for newly created dynamic elements to ensure the proper rules are applied
	};
}); 
define('xstyle/core/elemental', ['put-selector/put', 'xstyle/core/utils'], function(put, utils){
	// using delegation, listen for any input changes in the document and 'put' the value  
	// TODO: add a hook so one could add support for IE8, or maybe this event delegation isn't really that useful
	var doc = document;
	var nextId = 1;
	var hasAddEventListener = !!doc.addEventListener;
	var needsCapture = {
		blur: 'focusout',
		focus: 'focusin'
	};
	on(doc, 'change', null, inputChanged);
	// IE doesn't change on enter, and there isn't really any feature to detect to demonstrate that
	if (navigator.userAgent.match(/MSIE|Trident/)){
		on(doc, 'keydown', null, function(event){
			if(event.keyCode == 13){
				var element = event.target;
				if(document.createEvent){
					event = document.createEvent('Events');
					event.initEvent('change', true, true);
					element.dispatchEvent(event);
				}else{
					document.onchange({target: element});
				}
			}
		});
	}
	function inputChanged(event){
		var element = event.target;
		// get the variable computation so we can put the value
		for(var i = 0, l = inputConnectors.length; i < l; i++){
			var inputConnector = inputConnectors[i];
			// we could alternately use the matchesRule
			if((' ' + element.className + ' ').indexOf(inputConnector.rule.selector.slice(1)) > -1){
				var definition = inputConnector.definition;
				var currentValue = definition.valueOf();
				if(currentValue && currentValue.forRule){
					currentValue = currentValue.forRule(inputConnector.rule);
				}
				if(currentValue && currentValue.forElement){
					currentValue = currentValue.forElement(element);
				}
				var oldType = typeof currentValue;
				var value = element.type === 'checkbox' ? element.checked : element.value;
				// do type coercion
				if(oldType === 'number' && isFinite(value)){
					value = +value;
				}
				var result = inputConnector.definition.put(value);
				if(result && result.forRule){
					result = result.forRule(inputConnector.rule);
				}
				if(result && result.forElement){
					result.forElement(element);
				}
				// TODO: should we return here, now that we found a match?
			}
		}
	}
/*	sometime we might reimplement this, but for now just relying on dojo/on
right now, the main thing missing from this on implementation is the ability
to do capture
Have considered doing class name comparison, but any advantage is iffy:
http://jsperf.com/matches-vs-classname-check
*/
	function on(target, type, rule, listener){
		// this function can be overriden to provide better event handling
		hasAddEventListener ?
			target.addEventListener(type, select, !!needsCapture[type]) :
			ieListen(target, needsCapture[type] || type, select);
		function select(event){
			// do event delegation
			if(!rule){
				return listener(event);
			}
			var element = event.target;
			do{
				if(matchesRule(element, rule)){
					return listener(event);
				}
			}while((element = element.parentNode) && element.nodeType === 1);
		}
	}
	function ieListen(target, type, listener){
		type = 'on' + type;
		var previousListener = target[type];
		target[type] = function(event){
			event = event || window.event;
			event.target = event.target || event.srcElement;
			if(previousListener){
				previousListener(event);
			}
			listener(event);
		};
	}

	// elemental section, this code is for property handlers that need to mutate the DOM for elements
	// that match it's rule
	var testDiv = doc.createElement('div');
	var features = {
		'dom-qsa2.1': !!testDiv.querySelectorAll
	};
	function has(feature){
		return features[feature];
	}
	// get the matches function, whatever it is called in this browser	
	var matchesSelector = testDiv.matches || testDiv.matchesSelector ||
		testDiv.webkitMatchesSelector || testDiv.mozMatchesSelector ||
		testDiv.msMatchesSelector || testDiv.oMatchesSelector;
	var selectorRenderers = [];
	var inputConnectors = [];
	var renderQueue = [];
	var documentQueried;
	// probably want to inline our own DOM readiness code
	function domReady(callback){
		// TODO: support IE7-8
		if(/e/.test(doc.readyState||'')){
			// TODO: fix the issues with sync so this can be run immediately
			callback();
		}else{
			doc.addEventListener('DOMContentLoaded', callback);
		}
	}
	domReady(function(){
		if(!documentQueried){
			documentQueried = true;
			if(has('dom-qsa2.1')){
				// if we have a query engine, it is fastest to use that
				for(var i = 0, l = selectorRenderers.length; i < l; i++){
					// find the matches and register the renderers
					findMatches(selectorRenderers[i]);
				}
				// render all the elements that are queued up
				renderWaiting();
			}else{
			//else rely on css expressions (or maybe we should use document.all and just scan everything)
				var all = doc.all;
				for(var i = 0, l = all.length; i < l; i++){
					update(all[i]);
				}
			}
		}
	});
	function findMatches(renderer){
		// find the elements for a given selector and apply the renderers to it
		var results = doc.querySelectorAll(renderer.selector);
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
					// put it in the queue
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
	var isCurrent;
	function renderWaiting(){
		// render all the elements in the queue to be rendered
		while(renderQueue.length){
			var element = renderQueue.shift();
			var renderings = element.renderings, currentStyle = element.elementalStyle;
			while(renderings.length){
				var rendering = renderings.shift();
				var renderer = rendering.renderer;
				var rendered = renderer.rendered;
				// determine if this renderer matches the current computed style
				isCurrent = currentStyle[rendering.name] == renderer.propertyValue;
				if(!rendered && isCurrent){
					try{
						renderer.render(element);
					}catch(e){
						console.error(e, e.stack);
						put(element, 'div.error', e.toString());
					}
				}
				if(rendered && !isCurrent && renderer.unrender){
					renderer.unrender(element);
					//renderings.splice(j--, 1); // TODO: need to remove duplicate rendered items as well
				}
			}
			element.renderings = undefined;
		}
	}
	function update(element, selector){
		/* TODO: At some point, might want to use getMatchedCSSRules for faster access to matching rules
		if(typeof getMatchedCSSRules != 'undefined'){
			// webkit gives us fast access to which rules apply
			getMatchedCSSRules(element);
		}else{*/
		for(var i = 0, l = selectorRenderers.length; i < l; i++){
			var renderer = selectorRenderers[i];
			if((!selector || (selector == renderer.selector)) &&
				matchesRule(element, renderer.rule)){
				renderer.render(element);
			}
		}
	}
	var matchesRule = matchesSelector?
		function(element, rule){
			// use matchesSelector if available
			return matchesSelector.call(element, rule.selector);
		} :
		function(element, rule){
			// so we can match this rule by checking inherited styles
			if(!rule.ieId){
				rule.setStyle(rule.ieId = ('x-ie-' + nextId++), 'true');
			}
			// use IE's custom css property inheritance mechanism
			// TODO: determine if it is higher specificity that other  same name properties
			return !!element.currentStyle[rule.ieId];
		};

	function addInputConnector(rule, definition){
		inputConnectors.push({
			rule: rule,
			definition: definition
		});
	}
	function addRenderer(rule, handler){
		var renderer = {
			selector: rule.selector,
			rule: rule,
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
		return {
			remove: function(){
				selectorRenderers.splice(selectorRenderers.indexOf(renderer), 1);
			}
		};
	}
	return {
		ready: domReady,
		on: on,
		matchesRule: matchesRule,
		addRenderer: addRenderer,
		addInputConnector: addInputConnector,
		// this should be called for newly created dynamic elements to ensure the proper rules are applied
		update: update,
		clearRenderers: function(){
			// clears all the renderers in use
			selectorRenderers = [];
		},
		observeForElement: function(observable, rule, callback){
			return utils.when(observable, function(contextualizable){
				function observe(observable){
					if(observable.observe){
						observable.observe(callback);
					}else{
						callback(observable);
					}
				}
				if(contextualizable.forElement){
					addRenderer(rule, function(element){
						observe(contextualizable.forElement(element));
					});
				}else{
					observe(contextualizable);
				}
			});
		}
	};
});
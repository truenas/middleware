define("xstyle/core/base", ["xstyle/core/elemental", "xstyle/core/expression", "xstyle/core/utils", "put-selector/put", "xstyle/core/Rule"], 
function(elemental, evaluateExpression, utils, put, Rule){
	// this module defines the base definitions intrisincally available in xstyle stylesheets
	var truthyConversion = {
		'': 0,
		'false': 0,
		'true': 1
	};
	var styleSubstitutes = {
		display: ['none',''],
		visibility: ['hidden', 'visible'],
		'float': ['none', 'left']
	};
	var testDiv = put("div");
	var ua = navigator.userAgent;
	var vendorPrefix = ua.indexOf("WebKit") > -1 ? "-webkit-" :
		ua.indexOf("Firefox") > -1 ? "-moz-" :
		ua.indexOf("MSIE") > -1 ? "-ms-" :
		ua.indexOf("Opera") > -1 ? "-o-" : "";
	// we treat the stylesheet as a "root" rule; all normal rules are children of it
	var target, root = new Rule;
	root.root = true;
	function elementProperty(property, appendTo){
		// definition bound to an element's property
		// TODO: allow it be bound to other names, and use prefixing to not collide with element names
		return {
			forElement: function(element){
				var contentElement = element;
				// we find the parent element with an item property, and key off of that 
				while(!(property in element)){
					element = element.parentNode;
					if(!element){
						throw new Error(property + " not found");
					}
				}
				// provide a means for being able to reference the target node,
				// this primarily used by the generate model to nest content properly
				element['_' + property + 'Node'] = contentElement; 
				return {
					element: element, // indicates the key element
					receive: function(callback, rule){// handle requests for the data
						callback(element[property] || rule[property]);
					},
					appendTo: appendTo
				};
			},
			put: function(value, rule){
				rule[property] = value;
			}
		};
	}
	// the root has it's own intrinsic variables that provide important base and bootstrapping functionality 
	root.definitions = {
		Math: Math, // just useful
		module: function(mid){
			// require calls can be used to load in data in
			return {
				then: function(callback){
					require([mid], callback);
				}
			};
		},
		// TODO: add url()
		// adds support for referencing each item in a list of items when rendering arrays 
		item: elementProperty('item'),
		// adds referencing to the prior contents of an element
		content: elementProperty('content', function(target){
			target.appendChild(this.element);
		}),
		element: {
			// definition to reference the actual element
			forElement: function(element){
				return {
					element: element, // indicates the key element
					receive: function(callback){// handle requests for the data
						callback(element);
					},
					get: function(property){
						return this.element[property];
					}
				};				
			}
		},
		event: {
			receive: function(callback){
				callback(currentEvent);
			}
		},
		each: {
			put: function(value, rule, name){
				rule.each = value;
			}
		},
		prefix: {
			put: function(value, rule, name){
				// add a vendor prefix
				// check to see if the browser supports this feature through vendor prefixing
				if(typeof testDiv.style[vendorPrefix + name] == "string"){
					// if so, handle the prefixing right here
					// TODO: switch to using getCssRule, but make sure we have it fixed first
					rule.setStyle(vendorPrefix + name, value);
					return true;
				}
			}
		},
		// provides CSS variable support
		'var': {
			// setting the variables
			put: function(value, rule, name){
				(rule.variables || (rule.variables = {}))[name] = value;
				// TODO: can we reuse something for this?
				var variableListeners = rule.variableListeners;
				variableListeners = variableListeners && variableListeners[name] || 0;
				for(var i = 0;i < variableListeners.length;i++){
					variableListeners[i](value);
				}
			},
			// referencing variables
			call: function(call, rule, name, value){
				this.receive(function(resolvedValue){
					var resolved = value.toString().replace(/var\([^)]+\)/g, resolvedValue);
					// now check if the value if we should do subsitution for truthy values
					var truthy = truthyConversion[resolved];
					if(truthy > -1){
						var substitutes = styleSubstitutes[name];
						if(substitutes){
							resolved = substitutes[truthy];
						}
					}
					rule.setStyle(name, resolved);
				}, rule, call.args[0]);
			},
			// variable properties can also be referenced in property expressions
			receive: function(callback, rule, name){
				var parentRule = rule;
				do{
					var target = parentRule.variables && parentRule.variables[name] || 
						(parentRule.definitions && parentRule.definitions[name]); // we can reference definitions as well
					if(target){
						if(target.receive){
							// if it has its own receive capabilities, use that
							return target.receive(callback, rule, name);
						}
						var variableListeners = parentRule.variableListeners || (parentRule.variableListeners = {});
						(variableListeners[name] || (variableListeners[name] = [])).push(callback);
						return callback(target);
					}
					parentRule = parentRule.parent;
				}while(parentRule);
				callback();
			}
		},
		'extends': {
			call: function(call, rule){
				// TODO: this is duplicated in the parser, should consolidate
				var args = call.args;
				for(var i = 0; i < args.length; i++){ // TODO: merge possible promises
					return utils.extend(rule, args[i], console.error);
				}
			}
		},
		on: {
			put: function(value, rule, name){
				// add listener
				elemental.on(document, name.slice(3), rule.selector, function(event){
					currentEvent = event;
					var computation = evaluateExpression(rule, name, value);
					if(computation.forElement){
						computation = computation.forElement(event.target);
					}
					computation && computation.stop && computation.stop();
					currentEvent = null;
				});
			}
		},
		'@supports': {
			selector: function(rule){
				function evaluateSupport(expression){
					var parsed;
					if(parsed = expression.match(/^\s*not(.*)/)){
						return !evaluateSupport(parsed[1]);
					}
					if(parsed = expression.match(/\((.*)\)/)){
						return evaluateSupport(parsed[1]);
					}
					if(parsed = expression.match(/([^:]*):(.*)/)){
						// test for support for a property
						var name = utils.convertCssNameToJs(parsed[1]);
						var value = testDiv.style[name] = parsed[2];
						return testDiv.style[name] == value;
					}
					if(parsed = expression.match(/\w+\[(.*)=(.*)\]/)){
						// test for attribute support
						return put(parsed[0])[parsed[1]] == parsed[2];
					}
					if(parsed = expression.match(/\w+/)){
						// test for attribute support
						return utils.isTagSupported(parsed);
					}
					throw new Error("can't parse @supports string");
				}
				
				if(evaluateSupport(rule.selector.slice(10))){
				rule.selector = '';
				}else{
					rule.disabled = true;
				}
			}
		}
	};
	return root;
});
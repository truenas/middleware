define('xstyle/core/Rule', [
	'xstyle/core/expression',
	'xstyle/core/Definition',
	'put-selector/put',
	'xstyle/core/es6',
	'xstyle/core/utils'
], function(expression, Definition, put, lang, utils){

	// define the Rule class, our abstraction of a CSS rule		
	var create = Object.create || function(base){
		function Base(){}
		Base.prototype = base;
		return new Base();
	};

	var convertCssNameToJs = utils.convertCssNameToJs;
	function setStyle(style, name, value){
		// TODO: only surround with try/catch on IE
		try{
			style[name] = value;
		}catch(e){
		}
	}
	var operatorMatch = {
		'{': '}',
		'[': ']',
		'(': ')'
	};
	// these are the css properties that need to eventually be
	// recomputed
	var staleProperties = {
	};
	var testStyle = put('div').style;
	function Rule(){}
	Rule.prototype = {
		property: function(key){
			// basic property implementation to match the property API
			return (this._properties || (this._properties = {}))[key] || (this._properties[key] = new Proxy(this.get(key)));
		},
		eachProperty: function(onProperty){
			// iterate through each property on the rule
			var values = this.values || 0;
			for(var i = 0; i < values.length; i++){
				var name = values[i];
				onProperty.call(this, name || 'unnamed', values[name]);
			}
		},
		fullSelector: function(){
			// calculate the full selector, in case this is a nested rule we
			// determine the full selector using parent rules 
			return (this.parent ? this.parent.fullSelector() : '') + (this.selector || '') + ' ';
		},
		newRule: function(name){
			// called by the parser when a new child rule is encountered 
			var rule = (this.rules || (this.rules = {}))[name] = new Rule();
			rule.disabled = this.disabled;
			rule.parent = this;
			return rule;
		},
		newCall: function(name){
			// called by the parser when a function call is encountered
			var call = new Call(name);
			call.parent = this;
			return call;
		},
		addSheetRule: function(selector, cssText){
			// Used to add a new rule
			if(selector.charAt(0) != '@'){ // for now just ignore and don't add at-rules
				var styleSheet = this.styleSheet;
				var cssRules = styleSheet.cssRules || styleSheet.rules;
				var ruleNumber = this.ruleIndex > -1 ? this.ruleIndex : cssRules.length;
				try{
					// IE doesn't like an empty cssText
					styleSheet.addRule(selector, cssText || ' ', ruleNumber);
				}catch(e){
					// errors can be thrown for browser specific selectors
					if(!selector.match(/-(moz|webkit|ie)-/)){
						console.warn('Unable to add rule', selector, cssText);
					}
				}
				return cssRules[ruleNumber];
			}
		},
		onRule: function(){
			// called by parser once a rule is finished parsing
			var cssRule = this.getCssRule();
			if(this.installStyles){
				for(var i = 0; i < this.installStyles.length;i++){
					var pair = this.installStyles[i];
					setStyle(cssRule.style, pair[0], pair[1]);
				}
			}
		},
		setMediaSelector: function(selector){
			this.isMediaBlock = true;
			this.selector = selector;
		},
		setStyle: function(name, value){
			if(this.cssRule){
				setStyle(this.cssRule.style, name, value);
			}/*else if('ruleIndex' in this){
				// TODO: inline this
				this.getCssRule().style[name] = value;
			}*/else{
				(this.installStyles || (this.installStyles = [])).push([name, value]);
			}
		},
		getCssRule: function(){
			if(!this.cssRule){
				this.cssRule = this.addSheetRule(this.selector, this.cssText);
			}
			return this.cssRule;
		},
		get: function(key){
			// TODO: need to add inheritance? or can this be removed
			return this.values[key];
		},
		elements: function(callback){
			var rule = this;
			require(['xstyle/core/elemental'], function(elemental){
				elemental.addRenderer(rule, function(element){
					callback(element);
				});
			});
		},
		declareDefinition: function(name, value, conditional){
			name = name && convertCssNameToJs(name);
			// called by the parser when a variable assignment is encountered
			// this creates a new definition in the current rule
			if(this.disabled){
				return;
			}
			var rule = this;
			if(value.length){
				if(value[0].toString().charAt(0) == '>'){
					// this is used to indicate that generation should be triggered
					if(!name){
						this.generator = value;
						require(['xstyle/core/generate', 'xstyle/core/elemental'], function(generate, elemental){
							value = generate.forSelector(value, rule);
							elemental.addRenderer(rule, value);
						});
						return;
					}
				}else{
					// add it to the definitions for this rule
					var propertyExists = name in testStyle || this.getDefinition(name);
					if(!conditional || !propertyExists){
						var definitions = (this.definitions || (this.definitions = {}));
						var first = value[0];
						if(first.indexOf && first.indexOf(',') > -1){
							// handle multiple values
							var parts = value.join('').split(/\s*,\s*/);
							var definition = [];
							for(var i = 0;i < parts.length; i++){
								definition[i] = expression.evaluate(this, parts[i]);
							}
						}
						if(value[0] && value[0].operator == '{'){ // see if it is a rule
							definition = value[0];
						}else if(value[1] && value[1].operator == '{'){
							definition = value[1];
							utils.extend(definition, value[0]);
						}
						definition = definition || expression.evaluate(this, value);
						if(definition.then){
							// if we have a promise, create a new one to maintain lazy activation
							// and still check for a define function
							var originalDefinition = definition;
							definition = {
								then: function(callback){
									return originalDefinition.then(function(definition){
										return callback(applyDefine(definition));
									});
								}
							};
						}
						var applyDefine = function(definition){
							if(definition.define){
								definition = definition.define(rule, name);
							}
							return definition;
						};
						if(propertyExists){
							console.warn('Overriding existing property "' + name + '"');
						}
						return (definitions[name] = applyDefine(definition));
					}
				}
			}else{
				var definitions = (this.definitions || (this.definitions = {}));
				return (definitions[name] = value);
			}
		},
		onArguments: function(call){
			var handler = call.ref;
			// call the target with the parsed arguments
			return handler && handler.apply(this, call.getArgs(), this);
		},
		setValue: function(name, value, scopeRule){
			// called by the parser when a property is encountered
			var jsName = convertCssNameToJs(name);
			if(this.disabled){
				// TODO: eventually we need to support reenabling
				return;
			}
			var values = (this.values || (this.values = []));
			values.push(name);
			values[name] = value;
			// called when each property is parsed, and this determines if there is a handler for it
			// this is called for each CSS property
			if(name){
				var rule = this;
				do{
					// check for the handler
					var target = (scopeRule || this).getDefinition(name);
					if(target !== undefined){
						if(this.cssRule && !(target && target.keepCSSValue)){
							// delete the property if it one that the browser actually uses
							var thisStyle = this.cssRule.style;
							if(jsName in thisStyle){
								setStyle(thisStyle, jsName, '');
							}
						}
						contextualizeResultForRule(rule, target.put(value, rule, jsName));
					}
					// we progressively go through parent property names. For example if the 
					// property name is foo-bar-baz, it first checks for foo-bar-baz, then 
					// foo-bar, then foo
					name = name.substring(0, name.lastIndexOf('-'));
					// try shorter name
				}while(name);
			}
			if(jsName in testStyle){
				// if we don't have a handler, and this is a CSS property, we may need to
				// setup reactive bindings
				this._setStyleFromValue(jsName, value, true);
			}
		},
		_setStyleFromValue: function(propertyName, value, alreadySet){
			// This sets a CSS rule property from an unevaluated value
			var first = value[0];
			if(first instanceof Rule){
				// nested rule, that we can apply to sub-properties
				var values = first.values;
				for(var i = 0; i < values.length; i++){
					var key = values[i];
					this._setStyleFromValue(propertyName + (key == 'main' ? '' :
							key.charAt(0).toUpperCase() + key.slice(1)), values[key]);
				}
				return;
			}
			var calls = value.calls;
			if(calls){
				var rule = this;
				var expression = value.expression = evaluateText(value, this, propertyName, true);
				if(expression){
					var result = value.expression && value.expression.valueOf();

					var applyToRule = function(rule, invalidated){
						var value = result && result.forRule ? result.forRule(rule, true) : result;
						if(value && value.forElement){
							var elements = invalidated && invalidated.elements;
							if(elements){
								for(var i = 0; i < elements.length; i++){
									var subElements = elements[i].querySelectorAll(rule.selector);
									for(var j = 0; j < subElements.length; j++){
										var subElement = subElements[j];
										setStyle(subElement.style, propertyName, value.forElement(subElement));
									}
								}
							}else{
								forElement(rule, value, function(value, element){
									setStyle(element.style, propertyName, value);
								});
							}
							return;
						}
						// check to see if this is already overriden
						if(/*!inherited ||
								// if it is inherited, we need to check to make sure there isn't an existing property */
								true ||
								!rule.getCssRule().style[propertyName] ||
								// or if there is an existing, maybe it was inherited
								rule.inheritedStyles[propertyName]){
							rule.setStyle(propertyName, value);
						}
					};
					var appliedRules = [rule];
					utils.when(result, function(fulfilledResult){
						result = fulfilledResult;
						if(result && result.forRule){
							(rule._subRuleListeners || (rule._subRuleListeners = [])).push(function(rule){
								appliedRules.push(rule);
								applyToRule(rule);
							});
						}
						applyToRule(rule);
					});

					value.expression.dependencyOf({
						invalidate: function(invalidated){
							// TODO: queue these up
							//(rule.staleProperties || (rule.staleProperties = {}))[propertyName] =
							utils.when(value.expression.valueOf(), function(fulfilledResult){
								result = fulfilledResult;
								for(var i = 0; i < appliedRules.length; i++){
									var apply = true;
									var appliedRule = appliedRules[i];
									if(invalidated && invalidated.rules){
										apply = false;
										for(var j = 0; j < invalidated.rules.length; j++){
											if(invalidated.rules[j] === appliedRule){
												apply = true;
												break;
											}
										}
									}
									if(apply){
										applyToRule(appliedRule, invalidated);
									}
								}
							});
						}
					});
				}
			}
			if(!alreadySet){
				this.setStyle(propertyName, value);
			}
		},
		put: function(value){
			// rules can be used as properties, in which case they act as mixins
			// first extend
			var base = this;
			return {
				forRule: function(rule){
					base.extend(rule);
					if(value == 'defaults'){
						// this indicates that we should leave the mixin properties as is.
						return;
					}
					if(value && typeof value == 'string' && base.values){
						// then apply properties with comma delimiting
						var parts = value.toString().split(/,\s*/);
						for(var i = 0; i < parts.length; i++){
							// TODO: take the last part and don't split on spaces
							var name = base.values[i];
							name && rule.setValue(name, parts[i], base);
						}
					}
				}
			};
		},
		extend: function(derivative, fullExtension){
			// we might consider removing this if it is only used from put
			var base = this;
			(base.derivatives || (base.derivatives = [])).push(derivative);
			var newText = base.cssText;
			var extraSelector = base.extraSelector;
			if(extraSelector){
				// need to inherit any extra selectors by adding them to our selector
				derivative.selector += extraSelector;
			}
			// already have a rule, we use a different mechanism here
			var baseStyle = base.cssRule.style;
			var derivativeStyle = derivative.getCssRule().style;
			var inheritedStyles = derivative.inheritedStyles || (derivative.inheritedStyles = {});
			// now we iterate through the defined style properties, and copy them to the derivitative
			for(var i = 0; i < baseStyle.length; i++){
				var name = convertCssNameToJs(baseStyle[i]);
				// if the derivative has a style, we assume it is set in the derivative rule. If we 
				// inherit a rule, we have to mark it as inherited so higher precedence rules
				// can override it without thinking it came from the derivative. 
				if(!derivativeStyle[name] || inheritedStyles[name]){
					derivativeStyle[name] = baseStyle[name];
					inheritedStyles[name] = true;
				}
			}
			var baseValues = base.values;
			if(baseValues){
				baseValues = create(baseValues);
				var existingValues = derivative.values;
				derivative.values = existingValues ?
					lang.copy(baseValues, existingValues) : baseValues;
			}
			if(fullExtension){
				var baseDefinitions = base.definitions;
				if(baseDefinitions){
					baseDefinitions = create(baseDefinitions);
					var existingDefinitions = derivative.definitions;
					derivative.definitions = existingDefinitions ?
						lang.copy(baseDefinitions, existingDefinitions) : baseDefinitions;
				}
				derivative.tagName = base.tagName || derivative.tagName;
			}
			(derivative.bases || (derivative.bases = [])).push(base);
			var subRuleListeners = this._subRuleListeners || 0;
			for(var i = 0; i < subRuleListeners.length; i++){
				subRuleListeners[i](derivative);
			}
			var ruleStyle = derivative.getCssRule().style;
			base.eachProperty(function(name, value){
				var jsName = convertCssNameToJs(name);
				if(typeof value == 'object'){
					// make a derivative on copy
					value = create(value);
				}
				// just copy the native properties, the rest should be handled by rule listeners
				
				if(jsName in testStyle && !ruleStyle[jsName]){
					derivative._setStyleFromValue(jsName, value);
				}
		/*		if(name){
					name = convertCssNameToJs(name);
					if(!ruleStyle[name]){
						ruleStyle[name] = value;
					}
				}*/
			});

			if(existingValues && derivative.definitions){
				// now copy existing values, so any definition are properly applied
				for(var i = 0, l = existingValues.length; i < l; i++){
					var name = existingValues[i];
					var jsName = convertCssNameToJs(name);
					if(derivative.definitions[jsName] !== (existingDefinitions && existingDefinitions[jsName])){
						derivative.setValue(name, existingValues[jsName]);
					}
				}
			}
			var generator = base.generator;
			if(generator){
				// copy and subclass rules
				if(generator instanceof Array){
					generator = generator.slice(0);
					for(var i = 0; i < generator.length; i++){
						var segment = generator[i];
						if(segment.operator === '{'){
							// TODO: determine if it is contextualized to sub-rule, to determine
							// if we really need to extend/derive
							// make a derivative sub-rule
							var derivativeSegment = derivative.newRule();
							derivativeSegment.selector = segment.selector + derivative.selector.slice(1);
							derivativeSegment.styleSheet = derivative.styleSheet || derivative.cssRule.parentStyleSheet;
							segment.extend(derivativeSegment, true);
							generator[i] = derivativeSegment;
						}
					}
				}
				derivative.declareDefinition(null, generator);
			}
		},
		getDefinition: function(name, extraScope){
			name = convertCssNameToJs(name);
			// lookup a definition by name, which used for handling properties and other things
			var parentRule = this;
			do{
				var target = (parentRule.definitions && parentRule.definitions[name]);
				if(target === undefined && extraScope && parentRule[extraScope]){
					target = parentRule[extraScope][name];
				}
				parentRule = parentRule.parent;
			}while(target === undefined && parentRule);
			return target;
		},
		newElement: function(){
			return put((this.tagName || 'span') + (this.selector || ''));
		},
		cssText: ''
	};

	expression.evaluateText = evaluateText;
	function evaluateText(sequence, rule, name, onlyReturnEvaluated){
		var calls = sequence.calls;
		if(calls){
			var evaluatedCalls;
			for(var i = 0; i < sequence.length; i++){
				var part = sequence[i];
				if(part instanceof Call){
					if(!sequence.hasOwnProperty(i)){
						// it is derivative part, make a derivative call
						sequence[i] = part = create(part);
					}
					// evaluate each call
					var evaluated = part.ref && 
						(part.ref.selfResolving ? 
							part.ref.apply(rule, part.getArgs(), rule) :
							expression.evaluate(rule, [part.caller, part]));
					if(evaluated !== undefined){
						(evaluatedCalls || (evaluatedCalls = [])).push(evaluated);
						part.evaluated = true;
					}
				}
			}
		}
		if(evaluatedCalls){
			// react to the evaluated sequences
			var computation = expression.react(function(){
				var j = 0;
				var computedValue = sequence.slice();
				for(var i = 0; i < sequence.length; i++){
					var part = sequence[i];
					if(part instanceof Call && part.evaluated){
						// remove the caller string
						computedValue[i-1] = sequence[i-1].slice(0, -part.caller.length);
						// insert the current value
						computedValue[i] = arguments[j++];
					}
				}
				// now piece it together as a string
				return computedValue.join('');
			});
			computation.skipResolve = true;
			var definition = new Definition();
			definition.setCompute(computation.apply(definition, evaluatedCalls, definition));
			return definition;
		}
		if(!onlyReturnEvaluated){
			return sequence.toString();
		}
	}
	// a class representing function calls
	function Call(value){
		// we store the caller and the arguments
		this.caller = value;
		this.args = [];
	}
	var CallPrototype = Call.prototype = new Rule();
	CallPrototype.declareDefinition = CallPrototype.setValue = function(name, value){
		// handle these both as addition of arguments
		this.args.push(value);
	};
	CallPrototype.toString = function(){
		var operator = this.operator;
		return operator + this.args + operatorMatch[operator];
	};

	function contextualizeResultForRule(rule, result, callback, elementCallback){
		return utils.when(result, function(result){
			var startingResult = result;
			// TODO: we need to visit any derivatives
			if(result && result.forRule){
				(rule._subRuleListeners || (rule._subRuleListeners = [])).push(function(rule){
					var result = startingResult.forRule(rule, true);
					if(result && result.forElement){
						forElement(rule, result, elementCallback);
					}else{
						callback && callback(result);
					}
				});
				result = result.forRule(rule);
			}
			if(result && result.forElement){
				return forElement(rule, result, elementCallback);
			}else{
				callback && callback(result);
			}
		});
	}
	function forElement(rule, returned, elementCallback){	
		return require(['xstyle/core/elemental'], function(elemental){
			elemental.addRenderer(rule, function(element){
				var returnedFromElement = returned.forElement(element);
				elementCallback && elementCallback(returnedFromElement, element);
			});
		});
	}
	Rule.updateStaleProperties = function(){

	};
	return Rule;
});
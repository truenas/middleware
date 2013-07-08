define("xstyle/main", ["require", "put-selector/put"], function (require, put) {
	"use strict";
	// regular expressions used to parse CSS
	var cssScan = /\s*([^{\}\[\]\(\)\/\\'":=;]*)([=:]\??\s*([^{\}\[\]\(\)\/\\'":;]*))?([{\}\[\]\(\)\/\\'":;]|$)/g;
									// name: value 	operator
	var singleQuoteScan = /((?:\\.|[^'])*)'/g;
	var doubleQuoteScan = /((?:\\.|[^"])*)"/g;
	var commentScan = /\*\//g;
	var nextId = 0;
	// selection of default children for given elements
	var childTagForParent = {
		"TABLE": "tr",
		"TBODY": "tr",
		"TR": "td",
		"UL": "li",
		"OL": "li",
		"SELECT": "option"
	};
	var operatorMatch = {
		'{': '}',
		'[': ']',
		'(': ')'
	}
	var doc = document;
	// some utility functions
	function when(value, callback){
		return value && value.then ? 
			value.then(callback) : callback(value);
	}
	function get(target, path, callback){
		return when(target, function(target){
			var name = path[0];
			if(!target){
				return callback(name || target);
			}
			if(name && target.get){
				return get(target.get(name), path.slice(1), callback);
			}
			if(target.receive){
				return target.receive(name ? function(value){
					get(value, path, callback);
				} : callback);
			}
			if(name){
				return get(target[name], path.slice(1), callback);
			}
			callback(target);
		});
	}
	function set(target, path, value){
		get(target, path.slice(0, path.length - 1), function(target){
			var property = path[path.length - 1];
			target.set ?
				target.set(property, value) :
				target[property] = value;
		});
	}
	var trim = ''.trim ? function (str){
		return str.trim();
	} : function(str){
		return str.replace(/^\s+|\s+$/g, '');
	};
	var undef, testDiv = doc.createElement("div");
	function search(tag){
		// used to search for link and style tags
		var elements = doc.getElementsByTagName(tag);
		for(var i = 0; i < elements.length; i++){
			checkImports(elements[i]);
		}
	}
	function toStringWithoutCommas(){
		return this.join('');
	}
	function arrayWithoutCommas(array){
		array.toString = toStringWithoutCommas;
		return array;
	}
	function LiteralString(string){
		this.value = string;
	}
	LiteralString.prototype.toString = function(){
		return '"' + this.value.replace(/["\\\n\r]/g, '\\$&') + '"';
	}

	var ua = navigator.userAgent;
	var vendorPrefix = ua.indexOf("WebKit") > -1 ? "-webkit-" :
		ua.indexOf("Firefox") > -1 ? "-moz-" :
		ua.indexOf("MSIE") > -1 ? "-ms-" :
		ua.indexOf("Opera") > -1 ? "-o-" : "";
	// traverse the @imports to load the sources 
	function checkImports(element, callback, fixedImports){
		var sheet = element.sheet || element.styleSheet || element;
		var needsParsing = sheet.needsParsing, // load-imports can check for the need to parse when it does it's recursive look at imports 
			cssRules = sheet.rules || sheet.cssRules;
		function fixImports(){
			// need to fix imports, applying load-once semantics for all browsers, and flattening for IE to fix nested @import bugs
			require(["xstyle/load-imports"], function(load){
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
					if(/^'/.test(rule.style.content)){
						// this means we are in a built sheet, and can directly parse it
						// TODO: parse here
					}
				}
			}
		}
		// ok, determined that CSS extensions are in the CSS, need to get the source and really parse it
		parse(sheet.localSource || (sheet.ownerNode || sheet.ownerElement).innerHTML, sheet, callback);
	}
	parse.getStyleSheet = function(importRule, sequence){
		return importRule.styleSheet;
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
	
		// we store a map of custom handlers for custom properties, functions, and selectors 	
		var handlers = {property:{}};
		function addHandler(type, name, module){
			// add a handler, can be any type (property, function, selector)
			var handlersForType = handlers[type] || (handlers[type] = {});
			handlersForType[name] = module;
		}
		function addExtensionHandler(type){
			// add a meta-handler for the x-property, x-function, etc. selectors that are used
			// to register new custom handlers
			if(!handlers[type]){
				handlers[type] = {};
			}
			addHandler("selector", 'x-' + type, {
				onRule: function(rule){
					// found a selector, let's register it
					rule.eachProperty(function(name, value){
						var asString = value.toString();
						// we iterate through each part of the handler value, using the first one that applies
						// handler values usually look like: prefix, module(some/module)
						do{
							// do some simple parsing, we really only support default, native, and require(), so this can handle that
							var parts = asString.match(/([^, \(]+)(?:[, ]+(.+))?/);
							if(!parts){
								return;
							}
							var first = parts[1];
							if(first == 'module'){
								// add a handler with a module id provided so it can be asynchronously loaded with require()
								return addHandler(type, name, value[1].args[0]);
							}if(first == "default"){
								if(type == "pseudo"){
									// if it is pseudo, we test with a query
									try{
										doc.querySelectorAll("x:" + name);
										return;
									}catch(e){}
								}
							}else if(first == "prefix"){
							}else{
								return addHandler(type, name, function(){
									return value;
								});
							}
						}while(asString = parts[2]); // wasn't supported, keep try the next part
					});
				}
			});
		}
		addExtensionHandler("property"); // add x-property selector for registering properties
		addExtensionHandler("function");// add x-function selector for registering functions
		addExtensionHandler("pseudo");// add x-pseudo selector for registering pseudos

		// make these intrinsically registered
		handlers['function']['var'] = xstyle;
		handlers['function']['extends'] = xstyle;

		var waiting = 1;
		// determine base url
		var baseUrl = (styleSheet.href || location.href).replace(/[^\/]+$/,'');

		// define the Rule class		
		function Rule(){}
		Rule.prototype = {
			eachProperty: function(onProperty){
				// iterate through each property on the rule
				var values = this.values || 0;
				for(var i = 0; i < values.length; i++){
					var name = values[i];
					onProperty.call(this, name || 'unnamed', values[name]);
				}
			},
			fullSelector: function(){
				// calculate the full selector, in case this is a nested rule we determine the full selector using parent rules 
				return (this.parent ? this.parent.fullSelector() : "") + (this.selector || "") + " ";  
			},
			newRule: function(name){
				// called by the parser when a new child rule is encountered 
				return (this.rules || (this.rules = {}))[name] = new Rule();
			},
			newCall: function(name, sequence, rule){
				// called by the parser when a function call is encountered
				var call = new Call(name);
				return call; 
			},
			addSheetRule: function(selector, cssText){
				// Used to add a new rule
				if(cssText &&
					selector.charAt(0) != '@'){ // for now just ignore and don't add at-rules
					var ruleNumber = styleSheet.addRule(selector, cssText);
					if(ruleNumber == -1){
						ruleNumber = styleSheet.cssRules.length - 1;
					}
					return styleSheet.cssRules[ruleNumber];
				}
			},
			onRule: function(){
				// called by parser once a rule is finished parsing
				this.getCssRule();
			},
			getCssRule: function(){
				if(!this.cssRule){
					this.cssRule =this.addSheetRule(this.selector, this.cssText);
				}
				return this.cssRule;
			},
			get: function(key){
				// TODO: need to add inheritance? or can this be removed
				return this.values[key];
			},
			declareProperty: function(name, value, conditional){
				// called by the parser when a variable assignment is encountered
				if(value[0].toString().charAt(0) == '>'){
					// this is used to indicate that generation should be triggered
					if(!name){
						this.generator = value;
						value = generate(value, this);
						xstyle.addRenderer("", value, this, value);
						return;
					}
				}else{
					// add it to the variables for this rule
					var propertyExists = name in testDiv.style || resolveProperty(this, name);
					if(!conditional || !propertyExists){
						var properties = (this.properties || (this.properties = {}));
						properties[name] = value;
						if(propertyExists){
							console.warn('Overriding existing property "' + name + '"');
						}
					}
				}
			},
			setValue: function(name, value){
				// called by the parser when a property is encountered
				var values = (this.values || (this.values = []));
				values.push(name);
				values[name] = value;
				var calls = value.calls;
				if(calls){
					for(var i = 0; i < calls.length; i++){
						var call = calls[i];
						var handler = call.ref;
						if(handler && typeof handler.call == 'function'){
							handler.call(call, this, name, value);
						}
					}
				}
				// called when each property is parsed, and this determines if there is a handler for it
				//TODO: delete the property if it one that the browser actually uses
				// this is called for each CSS property
				if(name){
					var propertyName = name;
					do{
						// check for the handler
						var target = resolveProperty(this, name);
						if(target){
							var rule = this;
							// call the handler to handle this rule
							when(evaluateExpression(rule, name, target), function(target){
								target = target.splice ? target : [target];
								for(var i = 0; i < target.length; i++){
									var segment = target[i];
									if(segment.put(value, rule, name)){
										break;
									}
								}
							});
							break;
						}
						// we progressively go through parent property names. For example if the 
						// property name is foo-bar-baz, it first checks for foo-bar-baz, then 
						// foo-bar, then foo
						name = name.substring(0, name.lastIndexOf("-"));
						// try shorter name
					}while(name);
				}
			},
			cssText: ""
		};
		// a class representing function calls
		function Call(value){
			// we store the caller and the arguments
			this.caller = value;
			this.args = [];
		}
		var CallPrototype = Call.prototype = new Rule;
		CallPrototype.declareProperty = CallPrototype.setValue = function(name, value){
			// handle these both as addition of arguments
			this.args.push(value);
		};
		CallPrototype.toString = function(){
			var operator = this.operator;
			return operator + this.args + operatorMatch[operator]; 
		};
		
		// we treat the stylesheet as a "root" rule; all normal rules are children of it
		var target, root = new Rule;
		root.root = true;
		// the root has it's own intrinsic variables that provide important base and bootstrapping functionality 
		root.properties = {
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
			item: {
				// adds support for referencing each item in a list of items when rendering arrays 
				forElement: function(element){
					// we find the parent element with an item property, and key off of that 
					while(!element.item){
						element = element.parentNode;
					}
					return {
						element: element, // indicates the key element
						receive: function(callback){// handle requests for the data
							callback(element.item);
						}
					}
				}
			},
			prefix: {
				put: function(value, rule, name){
					// add a vendor prefix
					// check to see if the browser supports this feature through vendor prefixing
					if(typeof testDiv.style[vendorPrefix + name] == "string"){
						// if so, handle the prefixing right here
						return rule.addSheetRule(rule.selector, vendorPrefix + name +':' + value);
					}
				}
			},
			'var': {
				put: function(value, rule, name){
					(rule.variables || (rule.variables = {}))[name] = value;
					// TODO: can we reuse something for this?
					var variableListeners = rule.variableListeners;
					variableListeners = variableListeners && variableListeners[name] || 0;
					for(var i = 0;i < variableListeners.length;i++){
						variableListeners[i](value);
					}
				},
				call: function(call, rule, name, value){
					this.receive(function(resolvedValue){
						rule.addSheetRule(rule.selector, name + ': ' + value.toString().replace(/var\([^)]+\)/g, resolvedValue));
					}, rule, call.args[0]);
				},
				receive: function(callback, rule, name){
					var parentRule = rule;
					do{
						var target = parentRule.variables && parentRule.variables[name];
						if(target){
							var variableListeners = parentRule.variableListeners || (parentRule.variableListeners = {});
							(variableListeners[name] || (variableListeners[name] = [])).push(callback);
							return callback(target);
						}
						parentRule = parentRule.parent;
					}while(parentRule);
					callback();
				}
			},
			on: {
				put: function(value, rule, name){
					// TODO: implement this
					console.log("add event listener");
					evaluateExpression(rule, name, value);
				}
			}
		};
		// keep references
		root.css = textToParse;
		root.parse = parseSheet;
		
		function onRule(selector, rule){
			// check for selector handler
			rule.onRule();
			var handlerForName = handlers.selector[selector];
			if(handlerForName){
				handler(handlerForName, "onRule", rule);
			}
		}
		function onCall(identifier, value){
			// check for handler for a function call()
			var handlerForName = handlers['function'][identifier];
			if(handlerForName){
				handler(handlerForName, "onCall", identifier, value, value.args);
			}
		}
		function onPseudo(pseudo, rule){
			// check for pseudo handler
			var handlerForName = handlers.pseudo[pseudo];
			if(handlerForName){
				handler(handlerForName, "onPseudo", pseudo, rule);
			}
		}
		
		function handler(module, type, name, value){
			// module handler for properties, functions, etc., takes care of loading the target module
			if(module){
				var rule = target;
				var ruleHandled = function(text){
					if(typeof text == 'string'){
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
					// finished loading, this function will see if everything is done yet
					finishedLoad();
				};
				
				waiting++;
				var onLoad = function(module){
					try{
						// module is loaded, now exectue the appropriate function on the module (like onProperty)
						var result = module[type](name, value, rule, styleSheet);
						if(rule instanceof Call){
							rule.result = result;
						}
						// a module can also return a promise
						if(result && result.then){
							// a promise, return immediately defer handling
							result.then(ruleHandled, handleError);
						}else{
							// done
							ruleHandled(result);
						}
					}catch(e){
						handleError(e);
					}
					function handleError(error){
						// Add some error handling to give developers a better idea of where error occurs.
						// TODO: Add line number, and file name
						console.error('Error occurred processing ' + type.slice(2).toLowerCase() + ' ' + name + 
							(rule.operator == '{' ? (' in rule "' + rule.selector + '" {' + rule.cssText) : '') + '. ' + 
												error.message);
						if(error){
							console.error(error);
						}
					}
				}
				// load the module using the module id, or direclty use it if it is already loaded
				typeof module == "string" ? require([module], onLoad) : onLoad(module);					
			}
		}
		// tracks the stack of rules as they get nested
		var stack = [root];
		function parseSheet(textToParse, styleSheet){
			// parse the CSS, finding each rule
			function addInSequence(operand, dontAddToSelector){
				if(!dontAddToSelector){
					selector += operand;
				}
				if(sequence){
					// we had a string so we are accumulated sequences now
					sequence.push ?
						typeof sequence[sequence.length - 1] == 'string' && typeof operand == 'string' ?
							sequence[sequence.length - 1] += operand : // just append the string to last segment
							operand && sequence.push(operand) : // add to the sequence
						typeof sequence == 'string' && typeof operand == 'string' ?
							sequence += operand : // keep appending to the string
							sequence = arrayWithoutCommas([sequence, operand]); // start a new sequence array
				}else{
					sequence = operand;
				}
			}
			target = root; // start at root
			cssScan.lastIndex = 0; // start at zero
			var ruleIndex = 0, browserUnderstoodRule = true, selector = '', assignNextName = true;
			while(true){
				// parse the next block in the CSS
				// we could perhaps use a simplified regex when we are in a property value 
				var match = cssScan.exec(textToParse);
				// the next block is parsed into several parts that comprise some operands and an operator
				var operator = match[4],
					first = match[1],
					assignment = match[2],
					value = match[3],
					assignmentOperator, name, sequence,
					conditionalAssignment;
				value = value && trim(value);
				
				first = trim(first);
				if(assignNextName){
					// we are at the beginning of a new property
					if(assignment){
						// remember the name, so can assign to it
						selector = name = first;
						// remember the operator (could be ':' for a property assignment or '=' for a property declaration)
						assignmentOperator = assignment.charAt(0);
						conditionalAssignment = assignment.charAt(1) == '?';
					}else{
						selector = value = first;
					}
					// store in the sequence, the sequence can contain values from multiple rounds of parsing
					sequence = value;
					if(name || operator != '/'){
						// as long we haven't hit an initial comment, we have the assigned property name now, and don't need to assign again
						assignNextName = false;
					}
				}else{
					// subsequent part of a property
					value = value ? first + assignment : first;
					// add to the current sequence
					addInSequence(value);	
				}
				switch(operator){
					case "'": case '"':
						// encountered a quoted string, parse through to the end of the string and add to the current sequence
						var quoteScan = operator == "'" ? singleQuoteScan : doubleQuoteScan;
						quoteScan.lastIndex = cssScan.lastIndex; // find our current location in the parsing
						var parsed = quoteScan.exec(textToParse);
						if(!parsed){ // no match for the end of the string
							error("unterminated string");
						}
						var str = parsed[1]; // the contents of the string
						// move the css parser up to the end of the string position
						cssScan.lastIndex = quoteScan.lastIndex; 
						// push the string on the current value and keep parsing
						addInSequence(new LiteralString(str));
						continue;
					case '/':
						// we parse these in case it is a comment
						if(textToParse[cssScan.lastIndex] == '*'){
							// it's a comment, scan to the end of the comment
							commentScan.lastIndex = cssScan.lastIndex + 1;
							commentScan.exec(textToParse); // find the end
							cssScan.lastIndex = commentScan.lastIndex; // move the CSS parser to the end of the comment 
						}else{
							// not a comment, add the operator in the accumulating string
							addInSequence('/');
						}
						continue;
					case '\\':
						// escaping
						var lastIndex = quoteScan.lastIndex++;
						// add the escaped character to the sequence
						addInSequence(textToParse.charAt(lastIndex));
						continue;
					case '(': case '{': case '[':
						// encountered a new contents of a rule or a function call
						var newTarget;
						var doExtend = false;
						if(operator == '{'){
							// it's a rule
							assignNextName = true; // enter into the beginning of property mode					
							// add this new rule to the current parent rule
							addInSequence(newTarget = target.newRule(selector), true);
							
							// todo: check the type
							if(assignmentOperator){
								browserUnderstoodRule = false;
								if(!assignment || assignment.charAt(1) == '>'){
									sequence.creating = true;
								}
								if(assignmentOperator == '=' && value){
									// extend the referenced target value
									// TODO: create auto-generate class?
									doExtend = true;
								}
							}
							if(target.root && browserUnderstoodRule){
								// we track the native CSSOM rule that we are attached to so we can add properties to the correct rule
								newTarget.cssRule = styleSheet.cssRules[ruleIndex++];
							}
						}else{
							// it's a call, add it in the current sequence
							var callParts = value.match(/(.*?)([\w-]*)$/);
							addInSequence(newTarget = target.newCall(callParts[2], sequence, target));
							newTarget.ref = resolveProperty(target, callParts[2]);
							(sequence.calls || (sequence.calls = [])).push(newTarget);
						}
						// make the parent reference
						newTarget.parent = target;
						if(sequence.creating){
							// in generation, we auto-generate selectors so we can reference them
							newTarget.selector = '.x-generated-' + nextId++;
						}else{							
							newTarget.selector = target.root ? selector : target.selector + ' ' + selector;
						}
						if(doExtend){
							var ref = resolveProperty(target, value.match(/[^\s]+$/)[0], true);
							if(ref){
								extend(ref, newTarget);
							}
						}
						
						// store the current state information so we can restore it when exiting this rule or call
						target.currentName = name;
						target.currentSequence = sequence;
						target.assignmentOperator = assignmentOperator;
						// add to the stack
						stack.push(target = newTarget);
						target.operator = operator;
						target.start = cssScan.lastIndex;
						selector = '';
						// if it has a pseudo, call the pseudo handler
						target.selector && target.selector.replace(/:([-\w]+)/, function(t, pseudo){
							onPseudo(pseudo, target);
						});
						name = null;
						sequence = null;
						continue;
				}
				if(sequence){
					// now see if we need to process an assignment or directive
					var first = sequence[0];
					if(first.charAt && first.charAt(0) == "@"){
						// it's a directive
						if(sequence[0].slice(1,7) == "import"){
							// get the stylesheet
							var importedSheet = parse.getStyleSheet(styleSheet.cssRules[ruleIndex++], sequence, styleSheet);
							waiting++;
							// preserve the current index, as we are using a single regex to be shared by all parsing executions
							var currentIndex = cssScan.lastIndex;
							// parse the imported stylesheet
							parseSheet(importedSheet.localSource, importedSheet);
							// now restore our state
							cssScan.lastIndex = currentIndex;
						}
					}else{
						// need to do an assignment
						try{
							target[assignmentOperator == ':' ? 'setValue' : 'declareProperty'](name, sequence, conditionalAssignment);
						}catch(e){
							console.error(e.stack || e);
						}
					}
				}
				switch(operator){
					case ':':
						// assignment can happen after a property declaration
						assignNextName = true;
						assignmentOperator = ':';
						break;
					case '}': case ')': case ']':
						// end of a rule or function call
						// clear the name now
						if(operatorMatch[target.operator] != operator){
							console.error('Incorrect opening operator ' + target.operator + ' with closing operator ' + operator); 
						}
						name = null;
						// record the cssText
						target.cssText = textToParse.slice(target.start, cssScan.lastIndex - 1);
						if(operator == '}'){
							// if it is rule, call the rule handler 
							onRule(target.selector, target);
							// TODO: remove this conditional, now that we use assignment
							/*if(target.selector.slice(0,2) != "x-"){// don't trigger the property for the property registration
								target.eachProperty(onProperty);
							}*/
							browserUnderstoodRule = true;
							selector = '';
						}/*else if(operator == ')'){
							// call handler
							onCall(target.caller, target);
						}*/
						// now pop the call or rule off the stack and restore the state
						stack.pop();
						target = stack[stack.length - 1];				
						sequence = target.currentSequence;
						name = target.currentName;
						assignmentOperator = target.assignmentOperator;
						if(target.root && operator == '}'){
							// CSS ASI
							assignNextName = true;
							assignmentOperator = false;
						}
						break;
					case "":
						// no operator means we have reached the end of the text to parse
						callback && callback();
						return;
					case ';':
						// end of a property, end the sequence return to the beginning of propery mode
						sequence = null;
						assignNextName = true;
						browserUnderstoodRule = false;
						assignmentOperator = false;
						selector = '';
				}
			}
		}
		// call the parser
		parseSheet(textToParse,styleSheet);
		
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
		finishedLoad(target);
		return root;
	}

	// TODO: remove
	/*
	var rulesListeningToAttribute = {},
		reversalOfAttributes = {};
		
	function findAttributeInAncestors(element, tag, name, listeningRule){	
		var elementAncestor = element;
		if(listeningRule){
			// TODO: make it specific to tag as well
			var rules = (rulesListeningToAttribute[name] || (rulesListeningToAttribute[name] = []));
			rules.push(listeningRule); 
		}
		do{
			if(!tag || tag == elementAncestor.tagName){
				var value = elementAncestor[name];
				// if we have a callback, setup a listener
				if(listeningRule && xstyle.configDOMSetters){
					var oldDescriptor = Object.getOwnPropertyDescriptor(elementAncestor, name);
					var descriptor, setter = oldDescriptor && oldDescriptor.set;
					if(!setter){ // only if the a setter hasn't already been defined
						if(!descriptor){ // create the descriptor just once, and reuse
							// determine if we should call setAttribute
							var useSetAttribute = typeof value == 'string';							descriptor = {
								get: function(){
									return this._values && this._values[name];
								},
								set: function(value){
									(this._values || (this._values = {}))[name] = value;
									if(!callingFromSetAttribute){
										setAttribute(this, name, value, undefined, useSetAttribute);
									}
								}
							}
						}
						value && ((elementAncestor._values || (elementAncestor._values = {}))[name] = value);
						Object.defineProperty(elementAncestor, name, descriptor);
					}
				}
			}
		}while(!value && (elementAncestor != globalAttributes) && 
				(elementAncestor = elementAncestor.parentNode || globalAttributes));
		return value;
	}
	var callingFromSetAttribute;
	function setAttribute(element, name, value, put, useSetAttribute){
		callingFromSetAttribute = true;
		element[name] = value;
		callingFromSetAttribute = false;
		// set the attribute, the default action
		useSetAttribute && this.setAttribute(name, value);
		if(put !== true){
			var rules = rulesListeningToAttribute[name] || 0;
			for(var i = 0; i < rules.length; i++){
				var rule = rules[i];
				var nodeList = element.querySelectorAll(rule.selector);
				for(var j = 0; j < nodeList.length; j++){
					rule.recomputeAttribute(nodeList[j], name);
				}
			}
		}
		if(put !== false){
			var reversals = reversalOfAttributes[name] || 0;
			for(var i = 0; i < reversals.length; i++){
				var reversal = reversals[i];
				if(matchesSelector.call(element, reversal.rule.selector)){
					reversal(element, name, value);
				}
			}
		}
	}*/
	// using delegation, listen for any input changes in the document and "put" the value  
	// TODO: add a hook so one could add support for IE8, or maybe this event delegation isn't really that useful
	doc.addEventListener('change', function(event){
		var element = event.target;
		// get the variable computation so we can put the value
		var variable = element['-x-variable'];
		if(variable.put){ // if it can be put, we do so
			variable.put(element.value);
		}
	});


	// elemental section, this code is for property handlers that need to mutate the DOM for elements
	// that match it's rule
	var testDiv = doc.createElement("div");
	var features = {
		"dom-qsa2.1": !!testDiv.querySelectorAll
	};
	function has(feature){
		return features[feature];
	}
	// get the matches function, whatever it is called in this browser	
	var matchesSelector = testDiv.matches || testDiv.matchesSelector || testDiv.webkitMatchesSelector || testDiv.mozMatchesSelector || testDiv.msMatchesSelector || testDiv.oMatchesSelector;
	var selectorRenderers = [];
	var classHash = {}, propertyHash = {};
	var renderQueue = [];
	var documentQueried;
	// probably want to inline our own DOM readiness code
	function domReady(){
		// search the document for <link> and <style> elements to potentially parse.
		search('link');
		search('style');
		
		if(!documentQueried){
			documentQueried = true;
			if(has("dom-qsa2.1")){
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
	}
	// TODO: support IE7-8
	if(/e/.test(doc.readyState||'')){
		// TODO: fix the issues with sync so this can be run immediately
		setTimeout(domReady, 200);
	}else{
		doc.addEventListener("DOMContentLoaded", domReady);
	}
	function findMatches(renderer){
		// find the elements for a given selector and apply the renderers to it
		var toRender = [];
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
		for(var i = 0; i < renderQueue.length; i++){
			var element = renderQueue[i];
			var renderings = element.renderings, currentStyle = element.elementalStyle;
			delete element.renderings;
			for(var j = 0; j < renderings.length; j++){
				var rendering = renderings[j];
				var renderer = rendering.renderer;
				var rendered = renderer.rendered;
				isCurrent = currentStyle[rendering.name] == renderer.propertyValue; // determine if this renderer matches the current computed style
				if(!rendered && isCurrent){
					try{
						renderer.render(element);
					}catch(e){
						console.error(e, e.stack);
						put(element, "div.error", e.toString());
					}
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
	/* TODO: probably remove this:
	//window.put = window.put ? put : {};
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
		tagTriggers[element.tagName];
	}*/
	function update(element, selector){
	/* At some point, might want to use getMatchedCSSRules for faster access to matching rules 			
	 	if(typeof getMatchedCSSRules != "undefined"){
			// webkit gives us fast access to which rules apply
			getMatchedCSSRules(element);
		}else{*/
			for(var i = 0, l = selectorRenderers.length; i < l; i++){
			var renderer = selectorRenderers[i];
			if((!selector || (selector == renderer.selector)) &&
				(matchesSelector ?
					// use matchesSelector if available
					matchesSelector.call(element, renderer.selector) : // TODO: determine if it is higher specificity that other  same name properties
					// else use IE's custom css property inheritance mechanism
					element.currentStyle[renderer.name] == renderer.propertyValue)){
				renderer.render(element);
			}
		}
	}


	function generate(generatingSelector, rule){
		// this is responsible for generation of DOM elements for elements matching generative rules
		var id = nextId++;
		// normalize to array
		generatingSelector = generatingSelector.sort ? generatingSelector : [generatingSelector];
		// return a function that can do the generation for each element that matches
		return function(element, item){
			var lastElement = element;
			var subId = 0;
			for(var i = 0, l = generatingSelector.length;i < l; i++){
				// go through each part in the selector/generation sequence
				var part = generatingSelector[i];
				try{
					if(part.eachProperty){
						// it's a rule or call
						if(part.args){
							if(part.operator == '('){ // a call (or at least parans), for now we are assuming it is a binding
								var nextPart = generatingSelector[i+1];
								if(nextPart && nextPart.eachProperty){
									// apply the class for the next part so we can reference it properly
									put(lastElement, nextPart.selector);
								}
								// TODO: make sure we only do this only once
								var expression = part.args.toString();
								var apply = evaluateExpression(part, 0, expression);
								(function(element, lastElement){
									when(apply, function(apply){
										// TODO: assess how we could propagate changes categorically
										if(apply.forElement){
											apply = apply.forElement(lastElement);
											// now apply.element should indicate the element that it is actually keying or varying on
										}
										var textNode = element.appendChild(doc.createTextNode("Loading"));
										apply.receive(function(value){
											if(value && value.sort){
												// if it is an array, we do iterative rendering
												if(textNode){
													// remove the loading node
													textNode.parentNode.removeChild(textNode);
													textNode = null;
												}
												var eachHandler = nextPart && nextPart.eachProperty && nextPart.get('each');
												// if "each" is defined, we will use it render each item 
												if(eachHandler){
													eachHandler = generate(eachHandler, nextPart);
												}
												value.forEach(eachHandler ?
													function(value){
														// TODO: do this inside generate
														eachHandler(element, value);
													} :
													function(value){
														// if there no each handler, we use the default tag name for the parent 
														put(element, childTagForParent[element.tagName] || 'div', value);
													});
											}else{
												if("value" in element){
													// add the text
													element.value= value;
													// we are going to store the variable computation on the element
													// so that on a change we can quickly do a put on it
													// we might want to consider changing that in the future, to
													// reduce memory, but for now this probably has minimal cost
													element['-x-variable'] = apply; 
												}else{
													// put text in for Loading until we are ready
													// TODO: we should do this after setting up the receive in case we synchronously get the data 
													// if not an array, render as plain text
													textNode.nodeValue = value;
												}
											}
										}, rule, expression);
									});
								})(lastElement, element);
							}else{// brackets
								put(lastElement, part.toString());
							}
						}else{
							// it is plain rule (not a call), we need to apply the auto-generated selector, so CSS is properly applied
							put(lastElement, part.selector);
							// do any elemental updates
							xstyle.update(lastElement, part.selector);
						}
					}else if(typeof part == 'string'){
						// actual CSS selector syntax, we generate the elements specified
						if(part.charAt(0) == '='){
							part = part.slice(1); // remove the '=' at the beginning					
						}
						
						var children = part.split(',');
						for(var j = 0, cl = children.length;j < cl; j++){
							var child = children[j].trim();
							var reference = null;
							if(child){
								// TODO: inline our own put-selector code, and handle bindings
								child = child.replace(/\([^)]*\)/, function(expression){
									reference = expression;
								});
								var nextElement = put(j == 0 ? lastElement : element, child);
								if(item){
									// set the item property, so the item reference will work
									nextElement.item = item;
								}
								var nextPart = generatingSelector[i + 1];
								if(nextElement != lastElement && // avoid infinite loop if it is a nop selector
									(!nextPart || !nextPart.eachProperty) // if the next part is a rule, than it should be extending it already, so we don't want to double apply
									){
									xstyle.update(nextElement);
								}
								lastElement = nextElement;
							}
						}
					}else{
						// a string literal
						lastElement.appendChild(doc.createTextNode(part.value));
					}
				}catch(e){
					console.error(e, e.stack);
					lastElement.appendChild(doc.createTextNode(e));
				}
			}
			return lastElement;
		}
	}
	function evaluateExpression(rule, name, value){
		// evaluate a binding
		var binding = rule["var-expr-" + name];
		if(variables){
			return binding;
		}
		var variables = [], isElementDependent;
		variables.id = nextId++;
		var target, parameters = [], id = 0, callbacks = [],
			attributeParts, expression = value.join ? value.join("") : value.toString(),
			simpleExpression = expression.match(/^[\w_$\/\.-]*$/); 
		// Do the parsing and function creation just once, and adapt the dependencies for the element at creation time
		// deal with an array, converting strings to JS-eval'able strings
			// find all the variables in the expression
		expression = expression.replace(/("[^\"]*")|([\w_$\.\/-]+)/g, function(t, string, variable){
			if(variable){
				// for each reference, we break apart into variable reference and property references after each dot				
				attributeParts = variable.split('/');
				var parameterName = attributeParts.join('_');
				parameters.push(parameterName);
				variables.push(attributeParts);
				// first find the rule that is being referenced
				var firstReference = attributeParts[0];
				var target = resolveProperty(rule, firstReference);
				if(typeof target == 'string' || target instanceof Array){
					target = evaluateExpression(rule, firstReference, target);
				}else if(!target){
					throw new Error('Could not find reference "' + firstReference + '"');					
				}
				if(target.forElement){
					isElementDependent = true;
				}
				attributeParts[0] = target;
				// we will reference the variable a function argument in the function we will create
				return parameterName;
			}
			return t;
		})
	
		if(simpleExpression){
			// a direct reversible reference
			// no forward reactive needed
			if(name){
				// create the reverse function
				var reversal = function(element, name, value){
					when(findAttributeInAncestors(element, attributeParts[0], attributeParts[1]), function(target){
						for(var i = 2; i < attributeParts.length -1; i++){
							var name = attributeParts[i];
							target = target.get ?
								target.get(name) :
								target[name];
						}
						var name = attributeParts[i];
						if(target.set){
							target.set(name, value);
						}else{
							target[name] = value;
						}
					});
				};
				reversal.rule = rule;
//				(reversalOfAttributes[name] || (reversalOfAttributes[name] = [])).push(reversal);
			}
		}else{
			// it's a full expression, so we create a time-varying bound function with the expression
			var reactiveFunction = Function.apply(this, parameters.concat(['return xstyleReturn(' + expression + ')']));
		}
		variables.func = reactiveFunction;
		rule["var-expr-" + name] = variables;
		function getComputation(){
			var waiting = variables.length + 1;
			var values = [], callbacks = [];
			var result, isResolved;
			var done = function(i){
				return function(value){
					values[i] = value;
					waiting--;
					if(waiting <= 0){
						isResolved = true;
						result = reactiveFunction ? reactiveFunction.apply(this, values) : values[0];
						for(var j = 0; j < callbacks.length;j++){
							callbacks[j](result);
						}
					}
				};
			};
			if(reactiveFunction){
				for(var i = 0; i < variables.length; i++){
					var variable = variables[i];
					get(variable[0], variable.slice(1), done(i));
				}
			}else{
				var variable = variables[0];
				var value = {
					then: function(callback){
						callbacks.push(callback);
					}
				}
				when(variable[0], function(resolved){
					value = resolved;
					for(var j = 1; j < variable.length; j++){
						if(value && value.get){
							value = value.get(variable[j]);
						}else{
							value = {
								receive: function(callback){
									get(resolved, variable.slice(1), callback);
								},
								put: function(value){
									set(resolve, variable.slice(1), value);
								}
							};
							break;
						}
					}
					for(var j = 0; j < callbacks.length; j++){
						callbacks[j](value);
					}
				});
				return value;
				if(first && first.then){
					return {
						then: function(callback){
							get(variable[0], variable.slice(1), callback);
						}
					};
				}else{
					return variable;
				}
			}
			done(-1)();
			if(result && result.then){
				return result;
			}
			return {
				receive: function(callback){
					if(callbacks){
						callbacks.push(callback);
					}
					if(isResolved){
						callback(result);
					}
				}
			}
		}
		return rule["var-expr-" + name] = isElementDependent ? {
			forElement: function(element){
				// TODO: at some point may make this async
				var callbacks = [];
				var mostSpecificElement;
				var elementVariables = [];
				// now find the element that matches that rule, in case we are dealing with a child
				var parentElement = element;
				while(!matchesSelector.call(element, rule.selector)){
					element = element.parentNode;
				}
				for(var i = 0; i < variables.length; i++){
					var variable = variables[i];
					var target = variable[0];
					// now find the element that is keyed on
					if(target.forElement){
						target = variable[0] = target.forElement(parentElement);
					}
					// we need to find the most parent element that we need to vary on for this computation 
					var varyOnElement = target.element;
					if(parentElement != mostSpecificElement){
						while(parentElement != varyOnElement){
							if(parentElement == mostSpecificElement){
								return;
							}
							parentElement = parentElement.parentNode;
						}
						mostSpecificElement = parentElement;
					}
				}
				// make sure we indicate the store we are keying off of
				var computation = mostSpecificElement["expr-result-" + variables.id];
				if(!computation){
					mostSpecificElement["expr-result-" + variables.id] = computation = getComputation();
					computation.element = mostSpecificElement;
				}
				return computation;
			}
		} : getComputation();
	}
	function resolveProperty(rule, name, includeRules){
		var parentRule = rule;
		do{
			var target = parentRule.properties && parentRule.properties[name]
				|| (includeRules && parentRule.rules && parentRule.rules[name]);
			parentRule = parentRule.parent;
		}while(!target && parentRule);
		return target;
	}
	
	function extend(base, derivative){
		var newText = base.cssText;
		derivative.cssText += newText;
		'values,properties,variables,calls'.replace(/\w+/g, function(property){
			if(base[property]){
				derivative[property] = Object.create(base[property]);
			}
		});
		var cssRule = derivative.getCssRule();
		base.eachProperty(function(name, value){
			derivative.setValue(name, value);
			if(name){
				var ruleStyle = cssRule.style;
				if(!ruleStyle[name]){
					ruleStyle[name] = value;
				}
			}
		});
		if(base.generator){
			derivative.declareProperty(null, base.generator);
		}
		
	}
	var xstyle =  {
		process: checkImports,
		vendorPrefix: vendorPrefix,
		applyProperty: function(name, value){
			// basically a noop for most operations, we rely on the vendor prefixing in the main property parser 
			if(name == "opacity" && vendorPrefix == "-ms-"){
				return 'filter: alpha(opacity=' + (value * 100) + '); zoom: 1;';
			}
			return vendorPrefix + name + ':' + value + ';';
		},
		onFunction: function(name, value, rule){
		},
		onCall: function(name, rule){
			// handle extends(selector)
			var args = rule.args;
			var extendingRule = rule.parent;
			function resolve(){
				var parentRule = extendingRule;
				var namespace = name == 'extends' ? 'rules' : 'variables'; 
				do{
					if(!parentRule){
						throw new Error('Could not find "' + args[0] + '" in the defined ' + namespace);
					}
					var target = parentRule[namespace] && parentRule[namespace][args[0]];
					parentRule = parentRule.parent;
				}while(!target);
				return target;
			}
			if(name == 'extends'){
				var target = resolve();
				extend(target, extendingRule);
/*			}else if(name == 'bind'){
				var result = evaluateExpression(extendingRule, null, args[0]);
				if(result.forElement){
					// it is element dependent, this means we need to use inline styles
					xstyle.addRenderer();
				}else{
					result.receive(function(value){
						extendingRule.addSheetRule(extendingRule, name + ': ' + extendingRule.get(name).replace(/bind\([^)]+\)/g, target))
					});
				}*/
			}else if(name == 'var'){
				// TODO: do we need to reevaluate the value based on the new context?
				return function(parentRule){
					parentRule.addSheetRule(parentRule.selector, parentRule.currentName + ': ' + parentRule.currentSequence.toString().replace(/var\([^)]+\)/g, resolve()));
				};
			}
		},
		parse: parse,
		
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
		update: update, // this should be called for newly created dynamic elements to ensure the proper rules are applied
		clearRenderers: function(){
			// clears all the renderers in use
			selectorRenderers = [];
		},
		load:  function(resourceDef, require, callback, config){
			// support use an AMD plugin loader
			require(['xstyle/css'], function(plugin){
				plugin.load(resourceDef, require, callback, config);
			});
		}
	};
	return xstyle;

});
xstyleReturn = function(first){
	// global function used by the reactive functions to separate out comma-separated expressions into an array
	if(arguments.length == 1){
		// one arg, just return that
		return first;
	}
	// if it is a comma separated list of values, return them as an array
	return [].slice.call(arguments);
};

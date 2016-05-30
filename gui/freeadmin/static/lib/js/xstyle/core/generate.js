define('xstyle/core/generate', [
	'xstyle/core/elemental',
	'put-selector/put',
	'xstyle/core/utils',
	'xstyle/core/expression',
	'xstyle/core/base'
], function(elemental, put, utils, expressionModule, root){
	// this module is responsible for generating elements with xstyle's element generation
	// syntax and handling data bindings
	// selection of default children for given elements
	var childTagForParent = {
		TABLE: 'tr',
		TBODY: 'tr',
		TR: 'td',
		UL: 'li',
		OL: 'li',
		SELECT: 'option'
	};
	var inputs = {
		INPUT: 1,
		TEXTAREA: 1,
		SELECT: 1
	};
	var doc = document;
	var nextId = 1;
	function forSelector(generatingSelector, rule){
		// this is responsible for generation of DOM elements for elements matching generative rules
		// normalize to array
		generatingSelector = generatingSelector.sort ? generatingSelector : [generatingSelector];
		// return a function that can do the generation for each element that matches
		return function(element, item, beforeElement){
			var lastElement = element;
			var topElement;
			if(!('content' in element)){
				// a starting point for the content, so it can be detected by inheritance
				element.content = undefined;
			}
			// if this has been previously rendered, the content may be in the _contentNode
			if(beforeElement === undefined){
				var childNodes = (element._contentNode || element).childNodes || 0;
				var childNode = childNodes[0];
				// move the children out and record the contents in our content fragment
				if(childNode){
					var contentFragment = doc.createDocumentFragment();
					do{
						contentFragment.appendChild(childNode);
					}while((childNode = childNodes[0]));
					// temporarily store it on the element, so it can be accessed as an element-property
					// TODO: remove it after completion
					element.content = contentFragment;
				}
				if(element._contentNode){
					// need to clear the reference node, so we don't recursively try to put stuff in there,
					// and clean out of the current element
					element._contentNode = undefined;
					try{
						element.innerHTML = '';
					}catch(e){}
				}
			}
			var indentationLevel = 0;
			var indentationLevels = [element];
			var stackOfElementsToUpdate = [];
			for(var i = 0, l = generatingSelector.length;i < l; i++){
				// go through each part in the selector/generation sequence
				// TODO: eventually we should optimize for inserting nodes detached
				var lastPart = part,
					part = generatingSelector[i];
				try{
					if(part.eachProperty){
						// it's a rule or call
						if(part.args){
							if(part.operator == '('){ // a call (or at least parans), for now we are assuming it is a binding
								var nextPart = generatingSelector[i+1];
								bind(part, nextPart, lastElement, function(element, nextPart, expressionResult){
									renderContents(element, nextPart, expressionResult, rule);
								});
							}else{// brackets, set an attribute
								var attribute = part.args[0];
								if(typeof attribute === 'string'){
									var parts = attribute.split('=');
									try{
										lastElement.setAttribute(parts[0], parts[1]);
									}catch(e){
										// TODO: for older IE we need to use createElement for input names
										console.error(e);
									}
								}else{
									var name = attribute[0].replace(/=$/,'');
									var value = attribute[1];
									if(value.operator == '('){
										// a call/binding
										bind(attribute[1], name, lastElement, function(element, name, expressionResult){
											renderAttribute(element, name, expressionResult, rule);
										});
									}else{
										// a string literal
										lastElement.setAttribute(name, value.value);	
									}
								}
							}
						}//else{
							// it is plain rule (not a call), this should already be applied in element
							// generation
						//}
					}else if(typeof part == 'string'){
						// actual CSS selector syntax, we generate the elements specified
						if(part.charAt(0) == '='){
							part = part.slice(1); // remove the '=' at the beginning					
						}
				
						// TODO: inline our own put-selector code, and handle bindings
/*								child = child.replace(/\([^)]*\)/, function(expression){
									reference = expression;
								});
								/*if(!/^\w/.test(child)){
									// if it could be interpreted as a modifier, make sure we change it to really create a new element
									child = '>' + child;
								}*/
						var nextElement = lastElement;
						var nextPart = generatingSelector[i + 1];
						// parse for the sections of the selector
						var parts = [];
						part.replace(/([,\n]+)?([\t ]*)?(\.|#)?([-\w%$|\.\#]+)(?:\[([^\]=]+)=?['"]?([^\]'"]*)['"]?\])?/g, function(){
							parts.push(arguments);
						});
						// now iterate over these
						for(var j = 0;j < parts.length; j++){
							(function(t, nextLine, indentation, prefix, value, attrName, attrValue){
								function positionForChildren(){
									var contentNode = nextElement._contentNode;
									if(contentNode){
										// we have a custom element, that has defined a content node.
										contentNode.innerHTML = '';
										nextElement = contentNode;
									}
								}
								if(nextLine){
									var newIndentationLevel = indentation ? indentation.length : 0;
									if(newIndentationLevel > indentationLevel){
										positionForChildren();
										// a new child
										indentationLevels[newIndentationLevel] = nextElement;
									}else{
										// returning to an existing parent
										nextElement = indentationLevels[newIndentationLevel] || nextElement;
									}
									indentationLevel = newIndentationLevel;
								}else{
									positionForChildren();
								}
//								nextElement = element;
								var selector;
								if(prefix){// we don't want to modify the current element, we need to create a new one
									selector = (lastPart && lastPart.args ?
										// if the last part was brackets or a call, we can
										// continue modifying the same element
										'' :
										'span') + prefix + value;
								}else{
									var tagNameMatch = value.match(/^[-\w]+/);
									if(!tagNameMatch){
										throw new SyntaxError('Unable to parse selector', value);
									}
									var tagName = tagNameMatch[0];
									var target;
									if(j === parts.length - 1 && nextPart && nextPart.selector){
										// followed by a rule that should be applied
										if(!nextPart.bases){
											// apply extends first
											utils.extend(nextPart, tagName);
										}
										target = nextPart;
									} else {
										target = rule.getDefinition(tagName);
									}
									// see if we have a definition for the element
									if(target && (target.then || target.newElement)){
										nextElement = (function(nextElement, beforeElement, value, tagName){
											var newElement, placeHolder;
											// this may be executed async, we need to be ready with a place holder
											utils.when(target && target.newElement && target.newElement(), function(targetNewElement){
												newElement = targetNewElement;
												if(newElement){
													// apply the rest of the selector
													value = value.slice(tagName.length);
													if(value){
														put(newElement, value);
													}
												}else{
													newElement = put(value);
												}
												if(placeHolder){
													// a placeholder was created, replace it with the new element
													placeHolder.parentNode.replaceChild(newElement, placeHolder);
													var childNodes = placeHolder.childNodes;
													var childNode;
													// now move any children into the new element (or its content node)
													newElement = newElement._contentNode || newElement;
													while((childNode = childNodes[0])){
														newElement.appendChild(childNode);
													}
												}
											});
											if(newElement){
												// executed sync, just insert
												return nextElement.insertBefore(newElement, beforeElement || null);
											}else{
												// it was async, put in a placeholder
												var placeHolder = put('span');
												return nextElement.insertBefore(placeHolder, beforeElement || null);
											}
										})(nextElement, beforeElement, value, tagName);
									}else{
										selector = value;
									}
								}
								if(selector){
									nextElement = put(beforeElement || nextElement,
										(beforeElement ? '-' : '') + selector);
								}
								beforeElement = null;
								if(attrName){
									attrValue = attrValue === '' ? attrName : attrValue;
									nextElement.setAttribute(attrName, attrValue);
								}
								if(item){
									// set the item property, so the item reference will work
									nextElement.item = item;
								}
								topElement = topElement || nextElement;
								if(j < parts.length - 1 || (nextElement != lastElement &&
									// avoid infinite loop if it is a nop selector
									nextElement != element)){
									stackOfElementsToUpdate.push(j == parts.length - 1 && nextPart && nextPart.selector, nextElement);
								}
								lastElement = nextElement;
							}).apply(this, parts[j]);
						}
					}else{
						// a string literal
						lastElement.appendChild(doc.createTextNode(part.value));
					}
				}catch(e){
					console.error(e, e.stack);
					if(lastElement.innerHTML){
						lastElement.innerHTML = '';
					}
					lastElement.appendChild(doc.createTextNode(e));
				}
			}
			// now go back through and make updates to the elements, we do it in reverse
			// order so we can affect the children first
			var elementToUpdate;
			while((elementToUpdate = stackOfElementsToUpdate.pop())){
				elemental.update(elementToUpdate, stackOfElementsToUpdate.pop());
			}
			return topElement;
		};

	}

	function bind(part, nextPart, lastElement, render){
		var bindingSelector, bindingRule;
		if(nextPart && nextPart.eachProperty){
			// apply the class for the next part so we can reference it properly
			put(lastElement, bindingSelector = nextPart.selector);
			bindingRule = nextPart;
		}else{
			put(lastElement, bindingSelector = part.selector ||
				(part.selector = '.-xbind-' + nextId++));
			bindingRule = part;
		}
		var expression = part.getArgs()[0];
		var expressionResult = part.expressionResult;
		var expressionDefinition = part.expressionDefinition;
		// make sure we only do this only once

		if(!expressionDefinition){
			expressionDefinition = part.expressionDefinition =
				expressionModule.evaluate(part.parent, expression);
			expressionResult = expressionDefinition.valueOf();
			elemental.addInputConnector(bindingRule, expressionDefinition);
			(function(nextPart, bindingSelector, expressionDefinition){
				part.expressionResult = expressionResult;
				// setup an invalidation object, to rerender when data changes
				// TODO: fix this
				expressionDefinition.dependencyOf && expressionDefinition.dependencyOf({
					invalidate: function(invalidated){
						// TODO: should we use elemental's renderer?
						// TODO: do we need to closure the scope of any of these variables
						// TODO: might consider queueing or calling Object.deliverChangeRecords() or
						// polyfill equivalent here, to ensure all changes are delivered before 
						// rendering again
						var elementsToRerender;
						if(invalidated){
							if(elemental.matchesRule(invalidated.elements[0], bindingRule)){
								elementsToRerender = invalidated.elements;
							}else{
								elementsToRerender = invalidated.elements[0].querySelectorAll(bindingSelector);
							}
						}else{
							elementsToRerender = document.querySelectorAll(bindingSelector);
						}
						for(var i = 0, l = elementsToRerender.length;i < l; i++){
							render(elementsToRerender[i], nextPart, 
								expressionDefinition.valueOf());
						}
					}
				});
			})(nextPart, bindingSelector, expressionDefinition);
		}
		render(lastElement, nextPart, expressionResult);
	}

	function contextualize(value, rule, element, callback){
		return utils.when(value, function(value){
			if(value && value.forRule){
				value = value.forRule(rule);
			}
			if(value && value.forElement){
				value = value.forElement(element);
			}
			callback(value);
		});
	}

	function renderAttribute(element, name, expressionResult, rule){
		contextualize(expressionResult, rule, element, function(value){
			element.setAttribute(name, value);
		});
	}

	function renderContents(element, nextPart, expressionResult, rule){
		/*var contentProxy = element.content || (element.content = new Proxy());
		element.xSource = expressionResult;
		var context = new Context(element, rule);
		contentProxy.setValue(expressionResult);*/
		if(true || !('_defaultBinding' in element)){
			// if we don't have any handle for content yet, we install this default handling
			element._defaultBinding = true;
			if(expressionResult && expressionResult.then && element.tagName !== 'INPUT'){
				try{
					element.appendChild(doc.createTextNode('Loading'));
				}catch(e){
					// IE can fail on appending text for some elements,
					// TODO: we might want to only try/catch for IE, for performance
				}
			}
			contextualize(expressionResult, rule, element, function(value){
				if(element._defaultBinding){ // the default binding can later be disabled
					cleanup(element);
					if(element.childNodes.length){
						// clear out any existing content
						element.innerHTML = '';
					}
					if(value && value.sort){
						if(value.isSequence){
							forSelector(value, rule)(element);
						}else{
							// if it is an array, we do iterative rendering
							var eachHandler = nextPart && nextPart.definitions &&
								nextPart.definitions.each;
							// we create a rule for the item elements
							var eachRule = rule.newRule();
							// if 'each' is defined, we will use it render each item 
							if(eachHandler){
								eachHandler = forSelector(eachHandler, eachRule);
							}else{
								eachHandler = function(element, value, beforeElement){
									// if there no each handler, we use the default
									// tag name for the parent 
									return put(beforeElement || element, (beforeElement ? '-' : '') +
										(childTagForParent[element.tagName] || 'span'), '' + value);
								};
							}
							var rows = [];
							var handle;
							if(value.track){
								value = value.track();
								// TODO: cleanup routine
								handle = value.tracking;
							}
							value.forEach(function(value){
								// TODO: do this inside generate
								rows.push(eachHandler(element, value, null));
							});
							if(value.on){
								var onHandle = value.on('add,delete,update', function(event){
									var object = event.target;
									var previousIndex = event.previousIndex;
									var newIndex = event.index;
									if(previousIndex > -1){
										var oldElement = rows[previousIndex];
										cleanup(oldElement, true);
										oldElement.parentNode.removeChild(oldElement);
										rows.splice(previousIndex, 1);
									}
									if(newIndex > -1){
										rows.splice(newIndex, 0, eachHandler(element, object, rows[newIndex] || null));
									}
								});
							}
							handle = handle || onHandle;
							if(handle){
								element.xcleanup = function(){
									handle.remove();
								};
							}
						}
					}else if(value && value.nodeType){
						element.appendChild(value);
					}else{
						value = value === undefined ? '' : value;
						if(element.tagName in inputs){
							// set the text
							if(element.type === 'checkbox'){
								element.checked = value;
							}else{
								element.value = value;
							}
						}else{
							// render plain text
							element.appendChild(doc.createTextNode(value));							
						}
					}
				}
			});
		}
	}
	function cleanup(element, destroy){
		if(element.xcleanup){
			element.xcleanup(destroy);
		}
		var descendants = element.getElementsByTagName('*');
		for(var i = 0, l = descendants.length; i < l; i++){
			var descendant = descendants[i];
			descendant.xcleanup && descendant.xcleanup(true);
		}
	}
	function generate(parentElement, selector){
		return forSelector(selector, root)(parentElement);
	}
	generate.forSelector = forSelector;
	return generate;
});
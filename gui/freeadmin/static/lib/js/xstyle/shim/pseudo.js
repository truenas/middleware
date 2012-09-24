define("xstyle/shim/pseudo",[], function(){
	var attachedEvents = {};
	function handleEvent(eventType, add, className){
		if(!attachedEvents[eventType]){
			attachedEvents[eventType] = true;
			document.attachEvent(eventType, function(event){
				var style, element = event.srcElement;
				while(style = element.currentStyle){
					if(style.xstyle){
						if(add){
							element.className += " " + className;
						}else{
							(function(element){
								setTimeout(function(){
									element.className = (' ' + element.className + ' ').replace(' ' + className + ' ', ' ').slice(1);
								},0);
							})(element);
						}
					}
					element = element.parentNode;
				}
			});
		}
	}
	return {
		onPseudo: function(name, rule){
			if(name == "hover"){
				handleEvent("onmouseover", true, 'xstyle-hover');
				handleEvent("onmouseout", false, 'xstyle-hover');
				rule.add(rule.selector.replace(/:hover/, ''), 'xstyle: true');
				rule.add(rule.selector.replace(/:hover/, '.xstyle-hover'), rule.cssText);
			}else if(name == "focus"){
				handleEvent("onactivate", true, 'xstyle-focus');
				handleEvent("ondeactivate", false, 'xstyle-focusr');
				rule.add(rule.selector.replace(/:hover/, ''), 'xstyle: true');
				rule.add(rule.selector.replace(/:hover/, '.xstyle-focus'), rule.cssText);
			}
		}
	};
});

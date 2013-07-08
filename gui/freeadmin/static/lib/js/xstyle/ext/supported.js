define([], function(){
	var selectorParse = /(([-+])|[,<> ])?\s*(\.|!|#|:)?([-\w$]+)?(?:\[([^\]=]+)=?['"]?([^\]'"]*)['"]?\])?/g;
	return {
		onPseudo: function(name, rule){
			var supported = true;
			rule.selector.replace(selectorParse, function(t, combinator, siblingCombinator, prefix, value, attrName, attrValue){
				var element;
				if(value && !prefix){
					// test to see if the element tag name is supported
					var elementString = (element = document.createElement(value)).toString();
					if(elementString == "[object HTMLUnknownElement]" || elementString == "[object]"){
						supported = false;
						return;
					}
				}
				if(attrName){
					// test to see if the attribute is supported
					element.setAttribute(attrName, attrValue);
					if(element[attrName] != attrValue){
						supported = false;
					}
				}
			});
			if(supported == (name == "supported")){
				// match, add the rule without the pseudo
				rule.add(rule.selector = rule.selector.replace(/:(un)?supported/, ''), rule.cssText);
			}
		}
	};
});

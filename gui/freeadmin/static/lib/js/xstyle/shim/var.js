/*
    Handles CSS variables per http://dev.w3.org/csswg/css-variables/
*/
define([],function(vendor){
	return {
		onFunction: function(name, value, rule){
			var parentRule = rule;
			do{
				var target = parentRule.variables && parentRule.variables[name];
				parentRule = parentRule.parent;
			}while(!target);
			// TODO: do we need to reevaluate the value based on the new context? 
			rule.addSheetRule(rule.selector, name + ': ' + rule.get(name).replace(/var\([^)]+\)/g, target));
		}
	};
});


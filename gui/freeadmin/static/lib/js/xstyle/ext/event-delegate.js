define([], function(){
	var module, hasAddEventListener = !!document.addEventListener,
		div = document.createElement('div')
		matchesSelector = div.matchesSelector || div.webkitMatchesSelector || div.msMatchesSelector || div.mozMatchesSelector;
	return module = {
		// TODO: do an onCall function version for adding events that don't get overriden?
		onProperty: function(name, value, rule){
			var selector;
			// TODO: We could do a neat optimization of event handling with webkitMatchesRules, and delegating to the appropriate rule based on a hash map
			// we use event delegation
			this.on(document, name.slice(2), rule.fullSelector(), value);
		},
		on: function(target, event, selector, listener){
			// this function can be overriden to provide better event handling
			hasAddEventListener ? 
				target.addEventListener(event, select, false) :
				target.attachEvent(event, select);
			function select(event){
				selector = selector || rule.fullSelector();
				if(matchesSelector.call(event.target, selector)){
					console.log("execute event", listener);	
				}
			}
		}
	};
});
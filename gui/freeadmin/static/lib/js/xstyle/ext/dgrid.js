define([
	'dojo/_base/declare',
	'dojo/promise/all',
	'dojo/Deferred',
	'dojo/when',
	'./widget',
	'../core/expression'
], function(declare, all, Deferred, when, widgetModule, expression){
	var classNeeded = {
		'selectionMode': 'Selection',
		'columns': 'Grid',
		'keyboard': 'Keyboard'
	};
	var propertyHandlers = {
		'selectionMode': function(options, value){
			options.selectionMode = value;
		},
		'keyboard': function(options, value){
			options.cellNavigation = value == 'cell';
		},
		'collection': function(options, value, rule){
			value = expression.evaluate(rule, value);
			return when(value.valueOf(), function(value){
				options.collection = value;
			});
		},
		'columns': function(options, value){
			var columns = options.columns = {};
			value[0].eachProperty(function(name, value){
				var columnDefinition = widgetModule.parse(value[0]);
				columnDefinition.className = value[0].selector.slice(1);
				columns[name] = columnDefinition;
			});
			return columns;
		}
	};
	return {
		put: function(value, rule, name){
			name = name.slice(6);
			if(!rule.constructors){
				rule.constructors = ['dgrid/OnDemandList'];
				rule.handlers = [];
			}
			var config = value[0];
			var handlerCompletions = [];
			config.eachProperty(function(name, value){
				var handler = propertyHandlers[name];
				if(handler){
					var handlerCompletion = handler(config.values, value, rule);
					if(handlerCompletion){
						handlerCompletions.push(handlerCompletion);
					}
				}
				if(classNeeded[name]){
					rule.constructors.push('dgrid/' + classNeeded[name]);
				}
			});
			all(handlerCompletions).then(function(){
				widgetModule.parse(value[0], function(elementHandler){
						rule.elements(elementHandler);
				}, rule.constructors);
			});
		}
	};
});
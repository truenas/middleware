define(['dojo/_base/declare', 'dojo/promise/all', 'dojo/Deferred', 'dojo/when', './widget', '../core/expression'], function(declare, all, Deferred, when, widgetModule, evaluateExpression){
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
		'store': function(options, value, rule){
			var value = evaluateExpression(rule, 'store', value);
			when(value, function(value){
				options.store = value;
			});
			return value;
		},
		'columns': function(options, value){
			var columns = options.columns = {};
			var done;
			value[0].eachProperty(function(name, value){
				var columnDefinition = widgetModule.parse(value[0]);
				columnDefinition.className = value[0].selector.slice(1);
				if(columnDefinition.editor){
					// create an editor column, wait for it to load
					done = new Deferred();
					require(['dgrid/editor'], function (editor) {
						var parts = columnDefinition.editor.split(/,\s*/);
						columns[name] = editor(columnDefinition, parts[0], parts[1]);
						done.resolve();
					});
				}
				columns[name] = columnDefinition;
			});
			return done;
		}
	};
	var waiting;
	return {
		put: function(value, rule, name){
			name = name.slice(6);
			var moduleName = 'dgrid/' + classNeeded[name];
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
	}
});
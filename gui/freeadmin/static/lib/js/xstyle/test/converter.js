define(['xstyle/core/elemental'], function(elemental){
	var model = {
		data: '{\n  "first": "Web",\n  "last": "Developer",\n  "favorites": [\n    "Data Bindings", "CSS Extensions"\n  ]\n}', 
		ui: "#target {\n =>\n    h2 (data/first+' '+data/last),\n    ul (data/favorites) {\n      color: #060;\n    };\n  background-color: #ccc;\n  width: 200px;\n  padding: 10px;\n}", 
		parsed: {},
		schema: {
			data: new Property({
				coerce: coerceLiterals
			}),
			ui: new Property({
				coerce: coerceLiterals
			})
		}};
	function coerceLiterals(value){
		if(typeof value !== 'string' && value[0]){
			// a string literal
			value = value[0].value;
		}
		return value;
	}
	var registered = {};
	function updateJson(){
		var asJson = JSON.stringify(parsed.valueOf(), null, '  ');
		if(model.data !== asJson){
			model.set('data', asJson);
		}
	}
	function registerDataChanges(toWatch, model, registeredMap){
		registeredMap = registeredMap || registered;
		for(var i in toWatch){
			var property = model.property(i);
			if(!(i in registeredMap)){
				// listen for changes
				registeredMap[i] = true;
				property.observe(updateJson);
			}
			if(toWatch[i] && typeof toWatch[i] === 'object'){
				//registerDataChanges(toWatch[i], property, registeredMap[i]);
			}
		}
	}
	var parsed = model.property('parsed');
	model.observe('data', update);
	model.observe('ui', update);
	var parse, lastStyleSheet;
	function update(){
		console.log('model.data, model.ui', model.data, model.ui);
		var newSheet = createStyleSheet(model.ui);
		try{
			var data = JSON.parse(model.data);
			parsed.put(data);
			registerDataChanges(data, parsed);
			model.property('data').set('error', '');
		}catch(e){
			model.property('data').set('error', e);
		}
		setTimeout(function(){
			if(lastStyleSheet){
				// remove the last stylesheet
				document.head.removeChild(lastStyleSheet);
				elemental.clearRenderers();
				var target = document.getElementById("target");
				if(target){
					target.innerHTML = "";
				}
			}
			
			lastStyleSheet = newSheet;
			var error;
			var ui = model.property('ui');
			parse.onerror = function(e, message){
				ui.set('error', error = e + ' line' + message.slice(18));
			};
			try{
				parse(model.ui, lastStyleSheet.sheet);
				if(!error){
					ui.set('error','');
				}
			}catch(e){
				ui.set('error', e);
			}
		},100);
	}
	model.define = function(rule){
		do{
			parse = rule.parse;
			rule = rule.parent;
		}while(!parse);
		return model;
	}
	return model;
});
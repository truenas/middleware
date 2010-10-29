dojo.provide("dojango.form.Form");

dojo.require("dijit.form.Form");
dojo.require("dojo.date.stamp");

dojo.declare("dojango.form.Form", dijit.form.Form, {
	
	_getDojangoValueAttr: function(){
		// summary:
		// 	Custom get-value-method.
		// 	myForm.attr('dojangoValue') returns all form field values 
		// 	in a Django backend compatible format
		// 	myForm.attr("value") still can be used to retrieve the normal dijit.form.Form result
		var values = this.attr("value");
		return dojango.form.converter.convert_values(values);
	}
});

dojango.form.converter = {
	convert_values:function(/* Array */values){
		// summary:
		//	Converting a dictionary into valid values for the Django backend, e.g. JS Date Objects will
		//	be converted to 2009-01-01T00:00:00. This is used for converting all values of a form to a
		//	compatible format.
		//
		// values:Array
		//	Containing the values that should be converted
		for(var i in values){
			if(values[i] && ! values[i].getDate && dojo.isObject(values[i]) && !dojo.isArray(values[i])){
				values[i] = dojo.toJson(this._convert_value(values[i]));
			}
			else {
				values[i] = this._convert_value(values[i]);
			}
		}
		return values;
	},

	_convert_value:function(/* String|Object|Integer|Date */value){
		// summary:
		//	Returns a value that was converted into a django compatible format
		//
		// value: String|Object|Integer|Date
		//	The value that should be converted.
		if(value && value.getDate){
			value = dojo.date.stamp.toISOString(value);
			if(typeof(value) != "undefined"){
				// strip the timezone information +01:00
				// django/python does not support timezones out of the box!
				value = value.substring(0, value.length-6);
			}
		}
		else if(dojo.isString(value)){
			value = value;
			value = value.replace("<br _moz_editor_bogus_node=\"TRUE\" />", ""); // if a dijit.Editor field is empty in FF it always returns that
		}
		else if(dojo.isArray(value)){
			for(var i=0,l=value.length;i<l;i++){
				value[i] = this._convert_value(value[i]);
			}
		}
		else if(typeof(value) == "number" && isNaN(value)){ // just matches NaN
			value = "";
		}
		else if(dojo.isObject(value)){
			for(var i in value){
				value[i] = this._convert_value(value[i]); // recursive call, if the widget contains several values
			}
		}
		else if(typeof(value) == "undefined"){
			value = "";
		}
		return value;
	}
}
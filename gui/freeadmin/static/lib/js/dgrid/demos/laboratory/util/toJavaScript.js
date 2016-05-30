define([
	'dojo/_base/lang'
], function (lang) {
	// A basic check to ensure a property name is valid. Will incorrectly flag some valid names,
	// which is fine - they'll just get unnecessarily wrapped in quotes
	var propertyNameRegex = /^[A-Za-z]+[A-Za-z0-9_]*$/;

	// Check for dijit form widgets for editor property
	var dijitFormWidgetRegex = /dijit\/form\/([A-Za-z]*)$/;

	function tab(count) {
		var tabString = '';

		while (count--) {
			tabString += '\t';
		}

		return tabString;
	}

	/**
	 * @param {Object|Array} obj: object to convert to JavaScript
	 * @param {Object} options: option bag object
	 * @param {number} options.indent: (integer) indentation level of output code
	 * @param {boolean} options.includeEmpty: if true, empty properties ('', null, undefined) will be included in output
	 * @param {boolean} options.inline: if true, print just properties, not wrapping braces
	 */
	function toJavaScript(obj, options) {
		options = options || {};

		var javascript = '';
		var indent = options.indent || 0;

		// TODO: does not handle some things, e.g. null, undefined

		if (typeof obj === 'string') {
			return escapeString(obj);
		}

		if (typeof obj !== 'object') {
			return obj;
		}

		if (!options.inline) {
			if (obj instanceof Array) {
				javascript = '[';
			}
			else {
				javascript = '{';
			}

			javascript += '\n';
		}

		indent++;
		if (obj instanceof Array) {
			javascript += printArray(obj, lang.delegate(options, { inline: false }), indent);
		}
		else {
			javascript += printObject(obj, lang.delegate(options, { inline: false }), indent);
		}
		indent--;

		if (!options.inline) {
			javascript += '\n' + tab(indent);

			if (obj instanceof Array) {
				javascript += ']';
			}
			else {
				javascript += '}';
			}
		}

		return javascript;
	}

	function printObject(obj, options, indent) {
		var javascript = '';
		var property;
		var firstProperty = true;

		for (property in obj) {
			// TODO: filtering with hasOwnProperty may not be necessary (or desirable?)
			if (obj.hasOwnProperty(property)) {
				if ((options.includeEmpty ||
					(obj[property] !== '' && obj[property] !== null && obj[property] !== undefined))) {
					if (firstProperty) {
						firstProperty = false;
					}
					else {
						javascript += ',\n';
					}

					javascript += tab(indent) + formatPropertyName(property) + ': ';

					switch (typeof obj[property]) {
						// Array, Object
						case 'object':
							javascript += toJavaScript(obj[property], lang.delegate(options, { indent: indent }));

							break;

						case 'string':
							// Coerce string values that should be boolean
							if (obj[property] === 'true' || obj[property] === 'false') {
								javascript += obj[property];
							}
							else {
								// Widget editors are received by module ID, so convert any of those to constructors
								javascript += (property === 'editor' && formatDijitFormWidget(obj[property])) ||
									'\'' + escapeString(obj[property]) + '\'';
							}

							break;

						// number, boolean
						default:
							javascript += obj[property];
					}
				}
			}
		}

		return javascript;
	}

	function printArray(array, options, indent) {
		var javascript = '';
		var i;

		for (i = 0; i < array.length; i++) {
			javascript += tab(indent);
			javascript += toJavaScript(array[i], lang.delegate(options, { indent: indent }));

			if (i < array.length - 1) {
				javascript += ',\n';
			}
		}

		return javascript;
	}

	function escapeString(str) {
		return str.replace(/[\\']/g, '\\$&');
	}

	function formatDijitFormWidget(str) {
		return typeof str === 'string' && dijitFormWidgetRegex.test(str) ?
			str.replace(dijitFormWidgetRegex, '$1') :
			'';
	}

	function formatPropertyName(str) {
		if (!propertyNameRegex.test(str)) {
			return '\'' + str + '\'';
		}
		else {
			return str;
		}
	}

	toJavaScript.escapeString = escapeString;
	toJavaScript.formatDijitFormWidget = formatDijitFormWidget;
	toJavaScript.formatPropertyName = formatPropertyName;

	return toJavaScript;
});

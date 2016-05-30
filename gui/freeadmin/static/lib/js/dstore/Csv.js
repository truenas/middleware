define([
	'dojo/_base/lang',
	'dojo/_base/declare'
], function (lang, declare) {
	// originally from https://github.com/kfranqueiro/dojo-smore/blob/master/Csv.js
	var quoteRx = /^\s*"([\S\s]*)"\s*$/,
		doubleQuoteRx = /""/g,
		singleQuoteRx = /"/g;
	
	function arrays2hash(keys, values) {
		// Takes 2 arrays and builds a hash where the keys are from the first array,
		// and the values are from the second.
		var obj = {},
			len = keys.length,
			i;
		
		for (i = 0; i < len; i++) {
			obj[keys[i]] = values[i];
		}
		return obj;
	}
	
	return declare(null, {
		// summary:
		//		A store mixin for supporting CSV format.
		
		// fieldNames: Array?
		//		If specified, indicates names of fields in the order they appear in
		//		CSV records.  If unspecified, the first line of the CSV will be treated
		//		as a header row, and field names will be populated from there.
		fieldNames: null,
		
		// delimiter: String
		//		Delimiter between fields; default is a comma.
		delimiter: ',',
		
		// newline: String
		//		Character sequence to consider a newline.
		//		Defaults to '\r\n' (CRLF) as per RFC 4180.
		newline: '\r\n',
		
		// trim: Boolean
		//		If true, leading/trailing space will be trimmed from any unquoted values.
		trim: false,
		
		parse: function (str) {
			// handles the parsing of the incoming data as CSV.			

			var data = [],
				lines = str.split(this.newline),
				fieldNames = this.fieldNames,
				numquotes = 0, // tracks number of " characters encountered
				values = [], // records values in the current record
				value = '',
				prefix = '', // used to re-add delimiters and newlines to a spanning value
				parts, part, numlines, numparts, match,
				i, j, k;
			
			// Outer loop iterates over lines.  It's labeled so that inner loop
			// can jump out if an invalid value is encountered.
			lineloop:
			for (i = 0, numlines = lines.length; i < numlines; i++) {
				if (!lang.trim(lines[i])) { continue; } // ignore blank lines
				parts = lines[i].split(this.delimiter);
				
				// Inner loop iterates over "parts" (pieces of the line, split by
				// the configured delimiter).
				for (j = 0, numparts = parts.length; j < numparts; j++) {
					part = parts[j];
					k = -1;
					
					// Apply any leftovers in prefix before the next part, then clear it.
					value += prefix + part;
					prefix = '';
					
					// Count number of quotes in part to see whether we have a matching set.
					while ((k = part.indexOf('"', k + 1)) >= 0) { numquotes++; }
					
					if (numquotes % 2 === 0) {
						// Even number of quotes: we're done with this value.
						if (numquotes > 0) {
							match = quoteRx.exec(value);
							if (match) {
								// Good quoted string; unescape any quotes within.
								values.push(match[1].replace(doubleQuoteRx, '"'));
							} else {
								// If the completed value didn't match the RegExp, it's invalid
								// (e.g. quotes were inside the value but not surrounding it).
								// Jump out of the outer loop and start fresh on the next line.
								console.warn('Csv: discarding row with invalid value: ' + value);
								values = [];
								value = '';
								numquotes = 0;
								continue lineloop;
							}
						} else {
							// No quotes; push value as-is or trimmed.
							// (If this is the header row, trim regardless of setting.)
							values.push(this.trim || !fieldNames ? lang.trim(value) : value);
						}
						value = '';
						numquotes = 0;
					} else {
						// Open quoted value: add delimiter to current value on next run.
						// (i.e., we split on an instance of the delimiter character that is
						// actually *inside* a quoted value.)
						prefix = this.delimiter;
					}
				} // End of inner loop (delimited parts)
				
				if (numquotes === 0) {
					// Line ended cleanly, push values and reset.
					if (!fieldNames) {
						// We don't know any field names yet, so pick them up from the
						// first row of data.
						fieldNames = this.fieldNames = values;
					} else {
						data.push(arrays2hash(fieldNames, values));
					}
					values = [];
				} else {
					// We're in the middle of a quoted value with a newline in it,
					// so add a newline to it on the next iteration.
					prefix = this.newline;
				}
			} // End of outer loop (lines)
			
			// The data is assembled; return
			return data;
		},
		toCsv: function (options) {
			// summary:
			//		Returns data from Memory store, re-exported to CSV format.
			return this.stringify(this.data, options);
		},
		stringify: function (data, options) {
			// summary:
			//		Serializes data as CSV
			// options: Object?
			//		Optional object specifying options affecting the CSV output.
			//		* alwaysQuote: if true (default), all values will be quoted;
			//			if false, values will be quoted only if they need to be.
			//		* trailingNewline: if true, a newline will be included at the end
			//			of the string (after the last record).  Default is false.
			
			options = options || {};
			
			var alwaysQuote = options.alwaysQuote,
				fieldNames = this.fieldNames,
				delimiter = this.delimiter,
				newline = this.newline,
				output = '',
				i, j, value, needsQuotes;
			
			// Process header row first (-1 case), then all data rows.
			for (i = -1; i < data.length; i++) {
				if (i > -1) { output += newline; }
				for (j = 0; j < fieldNames.length; j++) {
					value = i < 0 ? fieldNames[j] : data[i][fieldNames[j]];
					if (value === null || value === undefined) {
						value = '';
					}
					if (typeof value !== 'string') {
						value = value.toString();
					}
					needsQuotes = alwaysQuote ||
						value.indexOf('"') >= 0 || value.indexOf(delimiter) >= 0;
					output += (j > 0 ? delimiter : '') +
						(needsQuotes ? '"' + value.replace(singleQuoteRx, '""') + '"' : value);
				}
			}
			
			if (options.trailingNewline) { output += newline; }
			
			return output;
		}
	});
});
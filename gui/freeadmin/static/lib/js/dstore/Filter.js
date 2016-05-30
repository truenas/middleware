define(['dojo/_base/declare'], function (declare) {
	// a Filter builder
	function filterCreator(type) {
		// constructs a new filter based on type, used to create each method
		return function newFilter() {
			var Filter = this.constructor;
			var filter = new Filter();
			filter.type = type;
			filter.args = arguments;
			if (this.type) {
				// we are chaining, so combine with an and operator
				return filterCreator('and').call(Filter.prototype, this, filter);
			}
			return filter;
		};
	}
	var Filter = declare(null, {
		constructor: function (filterArg) {
			var argType = typeof filterArg;
			switch (argType) {
				case 'object':
					var filter = this;
					// construct a filter based on the query object
					for (var key in filterArg){
						var value = filterArg[key];
						if (value instanceof this.constructor) {
							// fully construct the filter from the single arg
							filter = filter[value.type](key, value.args[0]);
						} else if (value && value.test) {
							// support regex
							filter = filter.match(key, value);
						} else {
							filter = filter.eq(key, value);
						}
					}
					this.type = filter.type;
					this.args = filter.args;
					break;
				case 'function': case 'string':
					// allow string and function args as well
					this.type = argType;
					this.args = [filterArg];
			}
		},
		// define our operators
		and: filterCreator('and'),
		or: filterCreator('or'),
		eq: filterCreator('eq'),
		ne: filterCreator('ne'),
		lt: filterCreator('lt'),
		lte: filterCreator('lte'),
		gt: filterCreator('gt'),
		gte: filterCreator('gte'),
		contains: filterCreator('contains'),
		'in': filterCreator('in'),
		match: filterCreator('match')
	});
	Filter.filterCreator = filterCreator;
	return Filter;
});
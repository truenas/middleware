define([
	'dojo/_base/declare',
	'../Memory'
],
function(declare, Memory) {
	// a very simple localStorage-based store, that basically loads everything
	// in memory and executes on it there. localStorage doesn't really provide
	// any real querying functionality, so might just as well do it all in memory
	return declare([Memory], {
		dbPrefix: 'dojo-db',
		storeName: 'default',
		constructor: function () {
			// load all the data from the local storage
			var data = [];
			var prefix = this.prefix = this.dbPrefix + '-' + this.storeName + '-';
			var store = this;
			for (var i = 0, l = localStorage.length; i < l; i++) {
				var key = localStorage.key(i);
				if (key.slice(0, prefix.length) === prefix) {
					data.push(store._restore(JSON.parse(localStorage.getItem(key))));
				}
			}
			this.setData(data);
		},
		putSync: function (object) {
			// addSync and all the async update methods eventually go through this
			var result = this.inherited(arguments);
			// prefix and store
			localStorage.setItem(this.prefix + this.getIdentity(object), JSON.stringify(object));
			return result;
		},
		removeSync: function (id) {
			localStorage.removeItem(this.prefix + id);
			return this.inherited(arguments);
		}
	});
});
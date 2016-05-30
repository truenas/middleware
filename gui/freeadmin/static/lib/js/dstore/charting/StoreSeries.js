define([
	'dojo/_base/lang',
	'dojo/_base/declare',
	'dojo/_base/array'
], function (lang, declare, array) {

	return declare(null, {
		constructor: function (collection, value) {
			// summary:
			//		Series adapter for dstore object stores.
			// collection: dstore/api/Store.Collection
			//		A dstore object store.
			// value: Function|Object|String
			//		Function, which takes an object handle, and
			//		produces an output possibly inspecting the store's item. Or
			//		a dictionary object, which tells what names to extract from
			//		an object and how to map them to an output. Or a string, which
			//		is a numeric field name to use for plotting. If undefined, null
			//		or empty string (the default), "value" field is extracted.
			this.collection = collection.track ? collection.track() : collection;

			if (value) {
				if (typeof value === 'function') {
					this.value = value;
				} else if (typeof value === 'object') {
					this.value = function (object) {
						var o = {};
						for (var key in value) {
							o[key] = object[value[key]];
						}
						return o;
					};
				} else {
					this.value = function (object) {
						return object[value];
					};
				}
			} else {
				this.value = function (object) {
					return object.value;
				};
			}

			this.data = [];

			this._initialRendering = false;
			this.fetch();
		},

		destroy: function () {
			// summary:
			//		Clean up before GC.
			var tracking = this.collection.tracking;
			tracking && tracking.remove();
		},

		setSeriesObject: function (series) {
			// summary:
			//		Sets a dojox.charting.Series object we will be working with.
			// series: dojox/charting/Series
			//		Our interface to the chart.
			this.series = series;
		},

		fetch: function () {
			// summary:
			//		Fetches data from the store and updates a chart.
			var collection = this.collection,
				update = lang.hitch(this, this._update);

			collection.fetch().then(lang.hitch(this, function (results) {
				this.objects = results;

				update();
				if (collection.tracking) {
					collection.on('add, update, delete', update);
				}
			}));
		},

		_update: function () {
			var self = this;
			this.data = array.map(this.objects, function (object) {
				return self.value(object, self.collection);
			});
			if (this.series) {
				this.series.chart.updateSeries(this.series.name, this, this._initialRendering);
				this._initialRendering = false;
				this.series.chart.delayedRender();
			}
		}
	});
});

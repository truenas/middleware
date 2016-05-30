define([
	'dojo/_base/declare',
	'dgrid/_StoreMixin'
], function (declare, _StoreMixin) {
	return declare(_StoreMixin, {
		// summary:
		//		dgrid mixin which implements the refresh method to
		//		always perform a single query with no start or count
		//		specified, to retrieve all relevant results at once.
		//		Appropriate for grids using memory stores with small
		//		result set sizes.
		//		From http://dgrid.io/tutorials/0.4/single_query/

		refresh: function () {
			var self = this;

			// First defer to List#refresh to clear the grid's
			// previous content
			this.inherited(arguments);

			if (!this._renderedCollection) {
				return;
			}

			return this._trackError(function () {
				return self.renderQueryResults(self._renderedCollection.fetch());
			});
		},

		renderArray: function () {
			var rows = this.inherited(arguments);

			// Clear _lastCollection which is ordinarily only used for store-less grids
			this._lastCollection = null;

			return rows;
		}
	});
});

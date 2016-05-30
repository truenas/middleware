define([
	'dojo/_base/declare'
	/*=====, 'dstore/Store'=====*/
], function (declare /*=====, Store=====*/) {
	return declare(null, {
		constructor: function () {
			this.root = this;
		},

		mayHaveChildren: function (object) {
			// summary:
			//		Check if an object may have children
			// description:
			//		This method is useful for eliminating the possibility that an object may have children,
			//		allowing collection consumers to determine things like whether to render UI for child-expansion
			//		and whether a query is necessary to retrieve an object's children.
			// object:
			//		The potential parent
			// returns: boolean

			return 'hasChildren' in object ? object.hasChildren : true;
		},

		getRootCollection: function () {
			// summary:
			//		Get the collection of objects with no parents
			// returns: dstore/Store.Collection

			return this.root.filter({ parent: null });
		},

		getChildren: function (object) {
			// summary:
			//		Get a collection of the children of the provided parent object
			// object:
			//		The parent object
			// returns: dstore/Store.Collection

			return this.root.filter({ parent: this.getIdentity(object) });
		}
	});
});

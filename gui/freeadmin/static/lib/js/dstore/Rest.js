define([
	'dojo/request',
	'dojo/when',
	'dojo/_base/lang',
	'dojo/json',
	'dojo/io-query',
	'dojo/_base/declare',
	'./Request' /*=====, './Store' =====*/
], function (request, when, lang, JSON, ioQuery, declare, Request /*=====, Store =====*/) {

	/*=====
	var __HeaderOptions = {
			// headers: Object?
			//		Additional headers to send along with the request.
		},
		__PutDirectives = declare(Store.PutDirectives, __HeaderOptions),
	=====*/

	return declare(Request, {

		// stringify: Function
		//		This function performs the serialization of the data for requests to the server. This
		//		defaults to JSON, but other formats can be serialized by providing an alternate
		//		stringify function. If you do want to use an alternate format, you will probably
		//		want to use an alternate parse function for the parsing of data as well.
		stringify: JSON.stringify,

		_getTarget: function(id){
			// summary:
			//		If the target has no trailing '/', then append it.
			// id:
			//		The identity of the requested target
			var target = this.target;
			if(target.slice(-1) == '/'){
				return target + id;
			}else{
				return target + '/' + id;
			}
		},

		get: function (id, options) {
			// summary:
			//		Retrieves an object by its identity. This will trigger a GET request to the server using
			//		the url `this.target + id`.
			// id: Number
			//		The identity to use to lookup the object
			// options: Object?
			//		HTTP headers. For consistency with other methods, if a `headers` key exists on this
			//		object, it will be used to provide HTTP headers instead.
			// returns: Object
			//		The object in the store that matches the given id.
			options = options || {};
			var headers = lang.mixin({ Accept: this.accepts }, this.headers, options.headers || options);
			var store = this;
			return request(this._getTarget(id), {
				headers: headers
			}).then(function (response) {
				return store._restore(store.parse(response), true);
			});
		},

		autoEmitEvents: false, // this is handled by the methods themselves

		put: function (object, options) {
			// summary:
			//		Stores an object. This will trigger a PUT request to the server
			//		if the object has an id, otherwise it will trigger a POST request.
			// object: Object
			//		The object to store.
			// options: __PutDirectives?
			//		Additional metadata for storing the data.  Includes an 'id'
			//		property if a specific id is to be used.
			// returns: dojo/_base/Deferred
			options = options || {};
			var id = ('id' in options) ? options.id : this.getIdentity(object);
			var hasId = typeof id !== 'undefined';
			var store = this;

			var positionHeaders = 'beforeId' in options
				? (options.beforeId === null
					? { 'Put-Default-Position': 'end' }
					: { 'Put-Before': options.beforeId })
				: (!hasId || options.overwrite === false
					? { 'Put-Default-Position': (this.defaultNewToStart ? 'start' : 'end') }
					: null);

			var initialResponse = request(hasId ? this._getTarget(id) : this.target, {
				method: hasId && !options.incremental ? 'PUT' : 'POST',
				data: this.stringify(object),
				headers: lang.mixin({
					'Content-Type': 'application/json',
					Accept: this.accepts,
					'If-Match': options.overwrite === true ? '*' : null,
					'If-None-Match': options.overwrite === false ? '*' : null
				}, positionHeaders, this.headers, options.headers)
			});
			return initialResponse.then(function (response) {
				var event = {};

				if ('beforeId' in options) {
					event.beforeId = options.beforeId;
				}

				var result = event.target = response && store._restore(store.parse(response), true) || object;

				when(initialResponse.response, function (httpResponse) {
					store.emit(httpResponse.status === 201 ? 'add' : 'update', event);
				});

				return result;
			});
		},

		add: function (object, options) {
			// summary:
			//		Adds an object. This will trigger a PUT request to the server
			//		if the object has an id, otherwise it will trigger a POST request.
			// object: Object
			//		The object to store.
			// options: __PutDirectives?
			//		Additional metadata for storing the data.  Includes an 'id'
			//		property if a specific id is to be used.
			options = options || {};
			options.overwrite = false;
			return this.put(object, options);
		},

		remove: function (id, options) {
			// summary:
			//		Deletes an object by its identity. This will trigger a DELETE request to the server.
			// id: Number
			//		The identity to use to delete the object
			// options: __HeaderOptions?
			//		HTTP headers.
			options = options || {};
			var store = this;
			return request(this._getTarget(id), {
				method: 'DELETE',
				headers: lang.mixin({}, this.headers, options.headers)
			}).then(function (response) {
				var target = response && store.parse(response);
				store.emit('delete', {id: id, target: target});
				return response ? target : true;
			});
		}
	});

});

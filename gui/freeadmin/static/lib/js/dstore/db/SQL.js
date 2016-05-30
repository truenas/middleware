define([
	'dojo/_base/declare',
	'dojo/Deferred',
	'dojo/when',
	'dstore/QueryResults',
	'dstore/Store',
	'dstore/SimpleQuery',
	'dojo/_base/lang',
	'dojo/promise/all'
], function (declare, Deferred, when, QueryResults, Store, SimpleQuery, lang, all) {
	//	summary:
	//		This module implements the dstore API using the WebSQL database
	function safeSqlName(name) {
		if (name.match(/[^\w_\.]/)) {
			throw new URIError('Illegal column name ' + name);
		}
		return name;
	}

	function getProperty(object, property) {
		var propertyPath = property.split('.');
		var pathLength = propertyPath.length;
		for (var i = 0; i < pathLength; i++) {
			object = object && object[propertyPath[i]];
		}
		return object;
	}

	function escapeDot(column) {
		return column.replace(/\./g, '_dot_');
	}

	var sqlOperators = {
		'and' : ' AND ',
		'or' : ' OR ',
		'eq' : '=',
		'ne' : '!=',
		'lte' : '<=',
		'gte' : '>=',
		'lt' : '<',
		'gt' : '>'
	};
	function convertExtra(object) {
		// converts the 'extra' data on sql rows that can contain expando properties outside of the defined column
		return object && object.__extra ? lang.mixin(object, JSON.parse(object.__extra)) : object;
	}
	return declare([Store, SimpleQuery], {
		constructor: function (config) {
			var dbConfig = config.dbConfig;
			// open the database and get it configured
			// args are short_name, version, display_name, and size
			this.database = openDatabase(config.dbName || 'dojo-db', '1.0', 'dojo-db', 4*1024*1024);
			var indexPrefix = this.indexPrefix = config.indexPrefix || 'idx_';
			var storeName = config.table || config.storeName;
			this.table = (config.table || config.storeName).replace(/[^\w]/g, '_');
			var promises = []; // for all the structural queries
			// the indices for this table
			this.indices = dbConfig.stores[storeName];
			this.repeatingIndices = {};
			for (var index in this.indices) {
				// we support multiEntry property to simulate the similar behavior in IndexedDB, we track these because we use the
				if (this.indices[index].multiEntry) {
					this.repeatingIndices[index] = true;
				}
			}
			if (!dbConfig.available) {
				// the configuration where we create any necessary tables and indices
				for (var storeName in dbConfig.stores) {
					var storeConfig = dbConfig.stores[storeName];
					var table = storeName.replace(/[^\w]/g, '_');
					// the __extra property contains any expando properties in JSON form
					var idConfig = storeConfig[this.idProperty];
					var indices = ['__extra', this.idProperty + ' ' + ((idConfig && idConfig.autoIncrement) ?
						'INTEGER PRIMARY KEY AUTOINCREMENT' : 'PRIMARY KEY')];
					var repeatingIndices = [this.idProperty];
					for (var index in storeConfig) {
						if (index != this.idProperty) {
							indices.push(escapeDot(index));
						}
					}
					promises.push(this.executeSql('CREATE TABLE IF NOT EXISTS ' + table+ ' ('
						+ indices.join(',') +
					')'));
					for (var index in storeConfig) {
						if (index != this.idProperty) {
							if (storeConfig[index].multiEntry) {
								// it is 'repeating' property, meaning that we expect it to have an array,
								// and we want to index each item in the array
								// we will search on it using a nested select
								repeatingIndices.push(index);
								var repeatingTable = table+ '_repeating_' + escapeDot(index);
								promises.push(this.executeSql('CREATE TABLE IF NOT EXISTS ' +
									repeatingTable + ' (id,value)'));
								promises.push(this.executeSql('CREATE INDEX IF NOT EXISTS idx_' +
									repeatingTable + '_id ON ' + repeatingTable + '(id)'));
								promises.push(this.executeSql('CREATE INDEX IF NOT EXISTS idx_' +
									repeatingTable + '_value ON ' + repeatingTable + '(value)'));
							}else{
								promises.push(this.executeSql('ALTER TABLE ' + table + ' ADD ' + escapeDot(index))
									.then(null, function () {
									/* suppress failed alter table statements*/
								}));
								// otherwise, a basic index will do
								if (storeConfig[index].indexed !== false) {
									promises.push(this.executeSql('CREATE INDEX IF NOT EXISTS ' + indexPrefix +
										table + '_' + escapeDot(index) + ' ON ' + table + '(' + escapeDot(index) + ')'));
								}
							}
						}
					}
				}
				dbConfig.available = all(promises);
			}
			this.available = dbConfig.available;
		},
		idProperty: 'id',
		selectColumns: ['*'],
		get: function (id) {
			// basic get() operation, query by id property
			var store = this;
			return when(this.executeSql('SELECT ' + this.selectColumns.join(',') + ' FROM ' +
					this.table + ' WHERE ' + this.idProperty + '=?', [id]), function (result) {
				return result.rows.length > 0 ? store._restore(convertExtra(result.rows.item(0))) : undefined;
			});
		},
		getIdentity: function (object) {
			return object[this.idProperty];
		},
		remove: function (id) {
			return this.executeSql('DELETE FROM ' + this.table + ' WHERE ' + this.idProperty + '=?', [id]); // Promise
			// TODO: remove from repeating rows too
		},
		identifyGeneratedKey: true,
		add: function (object) {
			// An add() wiill translate to an INSERT INTO in SQL
			var params = [], vals = [], cols = [];
			var extra = {};
			var actionsWithId = [];
			var store = this;
			function addColumn(column, value, originalColumn) {
				if (store.repeatingIndices[originalColumn || column]) {
					// we will need to add to the repeating table for the given field/column,
					// but it must take place after the insert, so we know the id
					actionsWithId.push(function(id) {
						return all(value.map(function(value) {
							return store.executeSql('INSERT INTO ' + store.table + '_repeating_' +
								column + ' (value, id) VALUES (?, ?)', [value, id]);
						}));
					});
				}else{
					// add to the columns and values for SQL statement
					cols.push(column);
					vals.push('?');
					params.push(value);
				}
			}

			for (var i in object) {
				if (object.hasOwnProperty(i)) {
					if (i in this.indices || i == this.idProperty) {
						addColumn(i, object[i]);
					}else{
						extra[i] = object[i];
					}
				}
			}
			// now handle nested property values, so they can be indexed
			for (var i in this.indices) {
				if (i.indexOf('.') > -1) {
					addColumn(escapeDot(i), getProperty(object, i), i);
				}
			}
			// add the 'extra' expando data as well
			cols.push('__extra');
			vals.push('?');
			params.push(JSON.stringify(extra));
			
			var idColumn = this.idProperty;
			if (this.identifyGeneratedKey) {
				params.idColumn = idColumn;
			}
			var sql = 'INSERT INTO ' + this.table + ' (' + cols.join(',') + ') VALUES (' + vals.join(',') + ')';
			return when(this.executeSql(sql, params), function (results) {
				var idDefinition = store.indices[idColumn];
				if (idDefinition && idDefinition.autoIncrement) {
					var id = results.insertId;
					object[idColumn] = id;
				} else {
					id = object[idColumn];
				}
				// got the id now, perform the insertions for the repeating data
				return all(actionsWithId.map(function(func) {
					return func(id);
				})).then(function() {
					return id;
				});
			});
		},
		put: function (object, directives) {
			// put, if overwrite is not specified, we have to do a get() to determine
			// if we need to do an INSERT INTO (via add), or an UPDATE
			directives = directives || {};
			var id = directives.id || object[this.idProperty];
			var overwrite = directives.overwrite;
			if (overwrite === undefined) {
				// can't tell if we need to do an INSERT or UPDATE, do a get() to find out
				var store = this;
				return this.get(id).then(function(previous) {
					if ((directives.overwrite = !!previous)) {
						directives.overwrite = true;
						return store.put(object, directives);
					}else{
						return store.add(object, directives);
					}
				});
			}
			if (!overwrite) {
				return store.add(object, directives);
			}
			var sql = 'UPDATE ' + this.table + ' SET ';
			var params = [];
			var cols = [];
			var extra = {};
			var store = this;

			function addColumn(column, value, originalColumn) {
				if (store.repeatingIndices[originalColumn || column]) {
					// update the repeating value tables
					store.executeSql('DELETE FROM ' + store.table + '_repeating_' + column + ' WHERE id=?', [id]);
					for (var j = 0; j < value.length; j++) {
						store.executeSql('INSERT INTO ' + store.table + '_repeating_' + column + ' (value, id) VALUES (?, ?)',
							[value[j], id]);
					}
				}else{
					cols.push(column + '=?');
					params.push(value);
				}
			}

			for (var i in object) {
				if (object.hasOwnProperty(i)) {
					if (i in this.indices || i == this.idProperty) {
						addColumn(i, object[i]);
					}else{
						extra[i] = object[i];
					}
				}
			}
			// now handle nested property values, so they can be indexed
			for (var i in this.indices) {
				if (i.indexOf('.') > -1) {
					addColumn(escapeDot(i), getProperty(object, i), i);
				}
			}
			cols.push('__extra=?');
			params.push(JSON.stringify(extra));
			// create the SETs for the SQL
			sql += cols.join(',') + ' WHERE ' + this.idProperty + '=?';
			params.push(object[this.idProperty]);

			return when(this.executeSql(sql, params), function () {
				return id;
			});
		},
		fetchRange: function (options) {
			return this.fetch(options);
		},
		generateSql: function () {
			var from = 'FROM ' + this.table;
			var condition = '';
			var order = '';
			var select = '*';
			var selectEntry;
			var store = this;
			var table = this.table;
			var params = [];
			this.queryLog.forEach(function (query) {
				if (query.type === 'filter') {
					condition = (condition ? ' AND ' : '') + convertFilter(query.normalizedArguments[0]).join('');
				} else if (query.type === 'sort') {
					order = ' ORDER BY ' + query.normalizedArguments[0].map(function(sort) {
						return sqlColumn(sort.property) + ' ' + (sort.descending ? 'desc' : 'asc');
					}).join(',');
				} else if (query.type === 'select') {
					var selectArgument = query.normalizedArguments[0];

					if (selectArgument instanceof Array) {
						for (var i = 0; i < selectArgument.length; i++){
							if (!(selectArgument[i] in store.indices)) {
								// can't use SQL SELECT to do the select since extra properties may be involved
								selectEntry = query;
								return;
							}
						}
						select = selectArgument.map(sqlColumn).join(', ');
					} else {
						if (selectArgument in store.indices) {
							select = sqlColumn(selectArgument);
						}
						// must always apply the select function to map to a single value per item
						selectEntry = query;
					}

				}
			});
			function sqlColumn(column) {
				safeSqlName(column);
				return table + '.' + escapeDot(column);	
			}
			function convertFilter(filter) {
				var args = filter.args;
				var column = args[0];
				var value = args[1];
				switch(filter.type) {
					case 'eq': case 'ne': case 'lt': case 'lte': case 'gt': case 'gte':
						params.push(value);
						return [sqlColumn(column), sqlOperators[filter.type] + '?'];
					case 'and': case 'or':
						var parts = [];
						for (var index = 0; index < args.length; index++) {
							parts.push(convertFilter(args[index]).join(''));
						}
						return ['(', parts.join(sqlOperators[filter.type]), ')'];
					case 'in':
						if (value.length === 0) {
							// an empty IN clause is considered invalid SQL
							return '0=1';
						} else if (value.generateSql) {
							var query = value.generateSql();
							params.push.apply(params, query.params);
							return [sqlColumn(column), ' IN (' + query.select + query.from + ')'];
						} else {
							return [sqlColumn(column), ' IN (' + args[1].map(function(value) {
								params.push(value);
								return '?';
							}).join(',') + ')'];
						}
						break;
					case 'contains':
						var repeatingTable = table + '_repeating_' + column;
						return ['(', value.map(function(value) {
							var condition;
							if (value && value.type) {
								condition = 'value ' + convertFilter(value).slice(1).join('');
							}else{
								params.push(value);
								condition = 'value=?';
							}
							return sqlColumn(store.idProperty) + ' IN (SELECT id FROM ' + repeatingTable + ' WHERE ' + condition + ')';
						}).join(' AND '), ')'];

					case 'match':
						value = value.source;
						if (value[0] === '^' && !value.match(/[\{\}\(\)\[\]\.\,\$\*]/)) {
							/* jshint quotmark: false */
							return [table + '.' + column, ' LIKE \'' + value.slice(1).replace(/'/g,"''") + '%\''];
						} else {
							throw new Error('The match filter only supports simple prefix matching like /^starts with/');
						}
						// js hint can't seem to tell that both branches break
						/* fall through */
					default:
						throw new URIError('Invalid query syntax, ' + filter.type + ' not implemented');
				}
			}
			if (condition) {
				condition = ' WHERE ' + condition;
			}

			return {
				select: 'SELECT ' + select + ' ',
				from: from + condition + order,
				params: params,
				querier: selectEntry && selectEntry.querier
			};
		},
		fetch: function (options) {
			options = options || {};
			var query = this.generateSql();
			var select = query.select;
			var from = query.from;
			var params = query.params;
			var querier = query.querier;

			var limitedCondition = select + ' ' + from;
			if (options.end) {
				limitedCondition += ' LIMIT ' + (options.end - (options.start || 0));
			}
			if (options.start) {
				limitedCondition += ' OFFSET ' + options.start;
			}
			var store = this;
			var results = lang.delegate(this.executeSql(limitedCondition, params).then(function(sqlResults) {
				// get the results back and do any conversions on it
				var results = [];
				for (var i = 0; i < sqlResults.rows.length; i++) {
					results.push(store._restore(convertExtra(sqlResults.rows.item(i))));
				}
				if (querier) {
					results = querier(results);
				}
				return results;
			}));
			var store = this;
			return new QueryResults(results, {
				totalLength: {
					then: function (callback,errback) {
						// lazily do a total, using the same query except with a COUNT(*) and without the limits
						return store.executeSql('SELECT COUNT(*) ' + from, params).then(function(sqlResults) {
							return sqlResults.rows.item(0)['COUNT(*)'];
						}).then(callback,errback);
					}
				}
			});
		},

		executeSql: function (sql, parameters) {
			// send it off to the DB
			var deferred = new Deferred();
			var result, error;
			this.database.transaction(function(transaction) {
				transaction.executeSql(sql, parameters, function (transaction, value) {
					deferred.resolve(result = value);
				}, function (transaction, e) {
					deferred.reject(error = e);
				});
			});
			// return synchronously if the data is already available.
			if (result) {
				return result;
			}
			if (error) {
				throw error;
			}
			return deferred.promise;
		}
		
	});
});

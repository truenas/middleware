define(['./db/has!indexeddb?./db/IndexedDB:sql?./db/SQL:./db/LocalStorage'],
	function(LocalDB){
	//	module:
	//		./store/LocalDB
	//	summary:
	//		The module defines an object store based on local database access
	return LocalDB;
});

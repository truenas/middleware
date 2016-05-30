define([
	'require',
	'dgrid/List',
	'dgrid/OnDemandGrid',
	'dgrid/Selection',
	'dgrid/Keyboard',
	'dgrid/extensions/ColumnHider',
	'dojo/_base/declare',
	'dojo/_base/array',
	'dojo/Stateful',
	'dojo/when',
	'dstore/RequestMemory',
	'put-selector/put',
	'dojo/domReady!'
], function (require, List, Grid, Selection, Keyboard, Hider, declare, arrayUtil, Stateful, when, RequestMemory, put) {
	// Create DOM
	var headerNode = put('div#header');
	var listNode = put('div#list-container');
	var genresNode = put(listNode, 'div#genres');
	var artistsNode = put(listNode, 'div#artists');
	var albumsNode = put(listNode, 'div#albums');
	var gridNode = put('div#grid');
	// Use require.toUrl for portability (looking up via module path)
	var songStore = new RequestMemory({ target: require.toUrl('./data.json') });

	put(document.body, headerNode, 'div#header-content', 'dTuned');
	put(document.body, listNode);
	put(document.body, gridNode);

	// a formatting function for the Duration column.
	function timeFormatter(t) {
		var tmp = parseInt(t, 10);
		var min;
		var sec;

		if (isNaN(tmp)) {
			return t;
		}

		min = Math.floor(tmp / 60);
		sec = tmp % 60;
		// don't forget to pad seconds.
		return '' + min + ':' + (sec < 10 ? '0' : '') + sec;
	}

	function unique(arr) {
		// Create a unique list of items from the passed array
		// (removing duplicates).
		var ret = [];

		// First, set up a hashtable for unique objects.
		var obj = {};
		for (var i = 0, l = arr.length; i < l; i++) {
			if (!(arr[i] in obj)) {
				obj[arr[i]] = true;
			}
		}

		// Now push the unique objects back into an array, and return it.
		for (var p in obj) {
			ret.push(p);
		}
		ret.sort();
		return ret;
	}

	function pickField(fieldName) {
		return function (object) {
			return object[fieldName];
		};
	}

	// Create the main grid to appear below the genre/artist/album lists.
	var grid = new (declare([Grid, Selection, Keyboard, Hider]))({
		collection: songStore,
		columns: {
			name: 'Name',
			time: { label: 'Duration', formatter: timeFormatter },
			year: 'Year',
			artist: 'Artist',
			album: 'Album',
			genre: 'Genre'
		}
	}, gridNode);

	// define a List constructor with the features we want mixed in,
	// for use by the three lists in the top region
	var TunesList = declare([List, Selection, Keyboard], {
		selectionMode: 'single'
	});

	// define our three lists for the top.
	var genresList = new TunesList({}, genresNode);
	var artistsList = new TunesList({}, artistsNode);
	var albumsList = new TunesList({}, albumsNode);

	// create the unique lists and render them
	var genres, artists, albums;

	songStore.fetch().then(function (songs) {
		genres = unique(arrayUtil.map(songs, pickField('genre')));
		artists = unique(arrayUtil.map(songs, pickField('artist')));
		albums = unique(arrayUtil.map(songs, pickField('album')));

		genres.unshift('All (' + genres.length + ' Genre' + (genres.length !== 1 ? 's' : '') + ')');
		artists.unshift('All (' + artists.length + ' Artist' + (artists.length !== 1 ? 's' : '') + ')');
		albums.unshift('All (' + albums.length + ' Album' + (albums.length !== 1 ? 's' : '') + ')');

		genresList.renderArray(genres);
		artistsList.renderArray(artists);
		albumsList.renderArray(albums);
	});

	// As items are selected in each of the genre, artist, and album dgrid lists the
	// associated value will be set on this stateful object so the main grid can
	// watch for updates and filter accordingly
	var gridFilter = new Stateful();

	// This function is used further down by the select handler for the artists list.
	// It builds a filtered list of album names depending on the selected genre and artist.
	function getFilteredAlbumList(gridFilter, songStore, selectedArtist) {
		var filterOptions = {};

		if (gridFilter.get('genre')) {
			filterOptions.genre = gridFilter.get('genre');
		}

		if (selectedArtist) {
			filterOptions.artist = selectedArtist;
		}

		return songStore.filter(filterOptions).fetch().then(function (filteredObjects) {
			var list = unique(arrayUtil.map(filteredObjects, pickField('album')));
			list.unshift('All (' + list.length +
				' Album' + (list.length !== 1 ? 's' : '') + ')');
			return list;
		});
	}

	gridFilter.watch(function () {
		var filter;

		if (this.genre || this.artist || this.album) {
			filter = {};

			if (this.genre) {
				filter.genre = this.genre;
			}
			if (this.artist) {
				filter.artist = this.artist;
			}
			if (this.album) {
				filter.album = this.album;
			}

			grid.set('collection', songStore.filter(filter));
		}
		else {
			if (grid.collection !== songStore) {
				grid.set('collection', songStore);
			}
		}
	});

	// start listening for selections on the lists.
	genresList.on('dgrid-select', function (event) {
		// filter the albums, artists and grid
		var row = event.rows[0];
		var selectedGenre = row.data;
		var filteredArtistList;

		if (row.id === '0') {
			// remove filtering
			gridFilter.set('genre', undefined);
			filteredArtistList = artists;
		}
		else {
			gridFilter.set('genre', selectedGenre);
			// filter the store on the current genre
			filteredArtistList = songStore.filter({ genre: selectedGenre }).fetch().then(function (filteredObjects) {
				// map the full album objects to a unique array of artist names (strings)
				var list = unique(arrayUtil.map(filteredObjects, pickField('artist')));
				// add the "All" option at the top
				list.unshift('All (' + list.length +
					' Artist' + (list.length !== 1 ? 's' : '') + ')');
				return list;
			});
		}

		when(filteredArtistList, function (list) {
			artistsList.refresh(); // clear contents
			artistsList.renderArray(list);
			artistsList.select('0'); // reselect "all", triggering albums+grid refresh
		});
	});

	artistsList.on('dgrid-select', function (event) {
		// filter the albums, grid
		var row = event.rows[0];
		var selectedArtist = row.data;
		var filteredAlbumList;

		if (row.id === '0') {
			gridFilter.set('artist', undefined);

			if (gridFilter.get('genre')) {
				// filter only by genre
				filteredAlbumList = getFilteredAlbumList(gridFilter, songStore);
			} else {
				// remove filtering entirely
				filteredAlbumList = albums;
			}
		}
		else {
			// create filter based on artist
			gridFilter.set('artist', selectedArtist);
			filteredAlbumList = getFilteredAlbumList(gridFilter, songStore, selectedArtist);
		}

		when(filteredAlbumList, function (list) {
			albumsList.refresh(); // clear contents
			albumsList.renderArray(list);
			albumsList.select('0'); // reselect "all" item, triggering grid refresh
		});
	});

	albumsList.on('dgrid-select', function (event) {
		// filter the grid
		var row = event.rows[0];
		var selectedAlbum = row.data;

		if (row.id === '0') {
			// show all albums
			gridFilter.set('album', undefined);
		} else {
			gridFilter.set('album', selectedAlbum);
		}
	});

	// set the initial selections on the lists.
	genresList.select('0');
});
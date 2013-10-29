#!/usr/bin/env node

var fs = require("fs"),
	path = require("path"),
	list = [], // stores list of files as they are scanned
	titleRx = /<title>([^<]+)/, // RegExp for scanning title tag
	internDirRx = /test\/intern\//, // RegExp for paths under the intern folder
	testDir = path.join(__dirname, ".."),
	filename = path.join(__dirname, "index.json");

function populateList(subdir) {
	// Populates the list variable with the names of all files under the given
	// path, including subdirectories.  This function is called recursively;
	// the initial call should not specify an argument.
	
	var dir = path.join(testDir, subdir),
		files = fs.readdirSync(dir),
		i, len, file, match;
	
	for (i = 0, len = files.length; i < len; i++) {
		file = files[i];
		if (path.extname(file) === ".html" && file !== "index.html" && !internDirRx.test(dir)) {
			match = titleRx.exec(fs.readFileSync(path.join(dir, file)));
			list.push({
				name: file, // filename only, for display purposes
				url: path.join(subdir, file), // relative to test folder, serves as ID
				title: match ? match[1] : "",
				parent: subdir || ""
			});
		} else if (fs.statSync(path.join(dir, file)).isDirectory() &&
				(file !== "data" && !internDirRx.test(dir + "/"))) {
			// Subdirectory found; add entry and recurse
			list.push({
				name: file,
				url: path.join(subdir, file),
				parent: subdir || ""
			});
			populateList(path.join(subdir, file));
		}
	}
}

populateList("");
fs.writeFileSync(filename, JSON.stringify(list, null, 4));
#!/usr/bin/env node

var fs = require("fs"),
	path = require("path"),
	list = [], // stores list of files as they are scanned
	rxTitle = /<title>([^<]+)/, // RegExp for scanning title tag
	testDir = path.join(__dirname, ".."),
	filename = path.join(__dirname, "index.json");

function populateList(subdir) {
	// Populates the list variable with the names of all files under the given
	// path, including subdirectories.  This function is called recursively;
	// the initial call should not specify an argument.
	
	var dir = path.join(testDir, subdir),
		files = fs.readdirSync(dir),
		i, len, file;
	
	for (i = 0, len = files.length; i < len; i++) {
		file = files[i];
		if (path.extname(file) === ".html" && file !== "index.html") {
			list.push({
				name: file, // filename only, for display purposes
				url: path.join(subdir, file), // relative to test folder, serves as ID
				title: rxTitle.exec(fs.readFileSync(path.join(dir, file)))[1],
				parent: subdir || ""
			});
		} else if (fs.statSync(path.join(dir, file)).isDirectory() && file !== "data") {
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

populateList();
fs.writeFileSync(filename, JSON.stringify(list, null, 4));
	var http = require('http');
	var put = require('put-selector');
	http.createServer(function (req, res) {
		res.writeHead(200, {'Content-Type': 'text/html'});
		var page = put('html').sendTo(res); // create an HTML page, and pipe to the response 
		put(page, 'head script[src=app.js]'); // each are sent immediately
		put(page, 'body div.content', 'Hello, World');
		page.end(); // close all the tags, and end the stream
	}).listen(81);
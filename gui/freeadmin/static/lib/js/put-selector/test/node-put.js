var assert = require("assert"),
	put = require("../put");
exports.testSimple = function() {
	assert.equal(put('div span.test<').toString(), '\n<div>\n  <span class="test"></span>\n</div>');
	assert.equal(put('div', ['header', 'section']).toString(), '\n<div>\n  <header></header>\n  <section></section>\n</div>');
};
exports.testPage = function() {
	put.indentation = false;
	var page = put('html');
	put(page, 'head script[src=test.js]+link[href=test.css]+link[href=test2.css]');
	var content = put(page, 'body div.header $\
			+div.content', 'Hello World');
	put(content, 'div.left', 'Left');
	put.addNamespace('foo', 'http://foo.com/foo');
	put(content, 'foo|bar');
	put(content, 'div.right', {innerHTML: 'Right <b>text</b>'});
	assert.equal(page.toString(), '<!DOCTYPE html>\n<html><head><script src=\"test.js\"></script><link href=\"test.css\"><link href=\"test2.css\"></head><body><div class=\"header\">Hello World</div><div class=\"content\"><div class=\"left\">Left</div><foo:bar></foo:bar><div class=\"right\">Right <b>text</b></div></div></body></html>');
};
exports.testStream = function() {
	//put.indentation = '  ';
	var output = '';
	var stream = {
		write: function(str){
			output += str;
		},
		end: function(str){
			output += str;
		}
	}
	var page = put('html').sendTo(stream);
	put(page, 'head script[src=test.js]+link[href=test.css]+link[href=test2.css]');
	var content = put(page, 'body div.header $\
			+div.content', 'Hello World');
	content.put('div.left', 'Left');
	content.put('div.right', {innerHTML: 'Right <b>text</b>'});
	page.end();
	assert.equal(output, '<!DOCTYPE html>\n<html><head><script src=\"test.js\"></script><link href=\"test.css\"><link href=\"test2.css\"></head><body><div class=\"header\">Hello World</div><div class=\"content\"><div class=\"left\">Left</div><div class=\"right\">Right <b>text</b></div></div></body>\n</html>');
};
if (require.main === module)
    require("patr/runner").run(exports);
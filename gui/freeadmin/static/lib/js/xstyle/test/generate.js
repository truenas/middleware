define([
	'intern!object',
	'intern/chai!assert',
	'xstyle/util/getComputedStyle',
	'xstyle/main',
	'xstyle/main!./core.css',
	'dojo/domReady!'
], function(registerSuite, assert, getComputedStyle, xstyle){
	var put = xstyle.generate;
	var id = 0;
	function testGenerator (params) {
		return function(){
			var elementId = 'generate-' + id++;
			xstyle.parse('test-var=4;#' + elementId + '{=>\n' + params.generator + '}', {cssRules: [], insertRule: function(){}});
			var newElement = put(document.body, '#' + elementId);
			params.check(newElement.firstChild);
		};
	}
	registerSuite({
		name: 'generate',
		simple: testGenerator({
			generator: 'div',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
			}
		}),
		attributeStatic: testGenerator({
			generator: 'div[title=hi]',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.title, 'hi');
			}
		}),
		attributeBinding: testGenerator({
			generator: 'div[title=(test-var)]',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.title, '4');
			}
		}),
		attributeBindingWithOperator: testGenerator({
			generator: 'div[title=(test-var + 3)]',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.title, '7');
			}
		}),
		attributeStringLiteral: testGenerator({
			generator: 'div[title="hello, world"]',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.title, 'hello, world');
			}
		}),
		className: testGenerator({
			generator: 'div.some-class',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.className, 'some-class');
			}
		}),
		testContents: testGenerator({
			generator: 'div(test-var)',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.innerHTML, '4');
			}
		}),
		testContentsWithOperator: testGenerator({
			generator: 'div(test-var+3)',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'DIV');
				assert.equal(newElement.innerHTML, '7');
			}
		}),
		testNesting: testGenerator({
			generator: 'ul li',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'UL');
				assert.equal(newElement.firstChild.tagName.toUpperCase(), 'LI');
				assert.equal(newElement.childNodes.length, 1);
			}
		}),
		testHierarchy: testGenerator({
			generator: 'ul\n li\n li\ndiv',
			check: function(newElement){
				assert.equal(newElement.tagName.toUpperCase(), 'UL');
				assert.equal(newElement.firstChild.tagName.toUpperCase(), 'LI');
				assert.equal(newElement.lastChild.tagName.toUpperCase(), 'LI');
				assert.equal(newElement.childNodes.length, 2);
				assert.equal(newElement.nextSibling.tagName.toUpperCase(), 'DIV');
			}
		})
	});
});
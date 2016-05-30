define([
	'intern!object',
	'intern/chai!assert',
	'dojo/on',
	'xstyle/util/getComputedStyle',
	'xstyle/main',
	'xstyle/core/base',
	'xstyle/main!./base.css',
	'dojo/domReady!'
], function(registerSuite, assert, on, getComputedStyle, xstyle, base){
	var put = xstyle.generate;
	registerSuite({
		name: 'base',
		prefix: function(){
			var testElement = put(document.body, 'test-prefix');
			if('WebkitAppearance' in testElement.style){
				assert.strictEqual(getComputedStyle(testElement).WebkitAppearance, 'button');
			}
		},
		expand: function(){
			var testElement = put(document.body, 'test-expand');
			var style = getComputedStyle(testElement);
			console.log("testElement", testElement.className);
			assert.strictEqual(style.marginTop, '1px');
			assert.strictEqual(style.marginRight, '2px');
			assert.strictEqual(style.marginBottom, '3px');
			assert.strictEqual(style.marginLeft, '1px');
		},
		testContent: function(){
			var testElement = put(document.body, 'div');
			testElement.innerHTML = 'hello';
			testElement.className = 'test-content';
			xstyle.update(testElement);
			assert.equal(testElement.firstChild.innerHTML, 'hello');
		},
		testEvent: function(){
			var testElement = put(document.body, 'test-event');
			var elementDispatched;
			base.definitions.testEvent = function(element){
				elementDispatched = element;
			};
			on.emit(testElement.firstChild, 'click', {bubbles: true});
			assert.equal(elementDispatched, testElement);
		}
	});
});
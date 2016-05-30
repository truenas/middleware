define([
	'intern!object',
	'intern/chai!assert',
	'xstyle/util/getComputedStyle',
	'xstyle/main',
	'xstyle/main!./core.css',
	'dojo/domReady!'
], function(registerSuite, assert, getComputedStyle, xstyle){
	var put = xstyle.generate;

	registerSuite({
		name: 'core',
		component: function(){
			var testComponent = put(document.body, 'test-component');
			assert.equal(testComponent.tagName, 'SECTION');
			var componentStyle = getComputedStyle(testComponent);
			assert.equal(componentStyle.borderBottomWidth, '4px');
			assert.equal(componentStyle.borderBottomColor, 'rgb(0, 0, 255)');
			assert.equal(componentStyle.color, 'rgb(0, 0, 255)');
			assert.equal(componentStyle.backgroundColor, 'rgb(221, 221, 221)');
			var testHeader = testComponent.firstChild;
			assert.equal(testHeader.tagName, 'H1');
			assert.isTrue(testHeader.className.indexOf('test-class') > -1);
			assert.equal(testHeader.innerHTML, 'Label');
			var headerStyle = getComputedStyle(testHeader);
			assert.equal(headerStyle.color, 'rgb(255, 0, 0)');
			var testContent = testHeader.nextSibling;
			assert.equal(testContent.innerHTML, 'The default content');
			var contentStyle = getComputedStyle(testContent);
			assert.equal(contentStyle.color, 'rgb(0, 128, 0)');
			assert.equal(contentStyle.width, '163px');
			var testDiv = testContent.nextSibling;
			assert.equal(testDiv.innerHTML, 'test from top');
		},

		'extend-by-property': function(){
			var testComponent = put(document.body, '.with-content');
			var componentStyle = getComputedStyle(testComponent);
			assert.equal(componentStyle.borderBottomWidth, '4px');
			assert.equal(componentStyle.borderBottomColor, 'rgb(170, 170, 170)');
			assert.equal(componentStyle.color, 'rgb(170, 170, 170)');
			assert.equal(componentStyle.backgroundColor, 'rgb(255, 255, 0)');
			var testHeader = testComponent.firstChild;
			assert.equal(testHeader.tagName, 'H1');
			assert.isTrue(testHeader.className.indexOf('test-class') > -1);
			assert.equal(testHeader.innerHTML, 'test');
			var headerStyle = getComputedStyle(testHeader);
			assert.equal(headerStyle.color, 'rgb(255, 0, 0)');
			var testContent = testHeader.nextSibling;
			assert.equal(testContent.innerHTML, 'The default content');
			var contentStyle = getComputedStyle(testContent);
			assert.equal(contentStyle.color, 'rgb(0, 128, 0)');
			assert.equal(contentStyle.width, '163px');
			var testDiv = testContent.nextSibling;
			assert.equal(testDiv.innerHTML, 'test from top');
		},	
		'extend-by-selector': function(){
			var testComponent = put(document.body, 'hello-world');
			var componentStyle = getComputedStyle(testComponent);
			assert.equal(componentStyle.borderBottomWidth, '4px');
			assert.equal(componentStyle.borderBottomColor, 'rgb(136, 136, 136)');
			assert.equal(componentStyle.color, 'rgb(136, 136, 136)');
			assert.equal(componentStyle.backgroundColor, 'rgb(255, 170, 170)');
			var testHeader = testComponent.firstChild;
			assert.equal(testHeader.tagName, 'H1');
			assert.isTrue(testHeader.className.indexOf('test-class') > -1);
			assert.equal(testHeader.innerHTML, 'Hello world');
			var headerStyle = getComputedStyle(testHeader);
			assert.equal(headerStyle.color, 'rgb(255, 0, 0)');
			var testContent = testHeader.nextSibling;
			assert.equal(testContent.innerHTML, 'The default content');
			var contentStyle = getComputedStyle(testContent);
			assert.equal(contentStyle.color, 'rgb(0, 128, 0)');
			assert.equal(contentStyle.width, '163px');
			var testDiv = testContent.nextSibling;
			assert.equal(testDiv.innerHTML, 'another test');
		},
		'extend-class': function(){
			var testComponent = put(document.body, 'test-class-extend');
			assert.isTrue(testComponent.className.indexOf('test-class1')> -1);
		},
		'extend-class2': function(){
			var testComponent = put(document.body, 'test-class-extend2');
			assert.isTrue(testComponent.className.indexOf('test-class1')> -1);
			assert.isTrue(testComponent.className.indexOf('test-class2')> -1);
		}

	});
});
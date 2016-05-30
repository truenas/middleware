define([
	'intern!object',
	'intern/chai!assert',
	'xstyle/core/parser',
	'xstyle/core/Rule'
], function(registerSuite, assert, parse, Rule){
	registerSuite({
		name: 'parser',
		'basic rule': function () {
			var rule = new Rule();
			parse(rule, 'test { property: value }');
			assert.strictEqual(rule.rules.test.get('property'), 'value');
		},
		comments: function () {
			var rule = new Rule();
			parse(rule, '/*test { property: value }*/');
			assert.strictEqual(rule.rules, undefined);
		},
		'nested scope' : function () {
			var rule = new Rule();
			parse(rule, '@xstyle start; test { property: value }');
			assert.strictEqual(rule.rules.test, undefined);
			assert.strictEqual(rule.rules[''].rules.test.get('property'), 'value');
		},
		'disabled' : function () {
			var rule = new Rule();
			parse(rule, '@xstyle end; test { property: value }');
			assert.strictEqual(rule.rules, undefined);
		},
		'preserve escapes' : function () {
			var rule = new Rule();
			parse(rule, 'test { content: "\\e001" }');
			assert.strictEqual(rule.rules.test.get('content')[0].value, '\ue001');
		},
		'font-face' : function () {
			var rule = new Rule();
			parse(rule, '@font-face {font-family: "Font Name";}');
			assert.strictEqual(rule.rules['@font-face'].get('fontFamily')[0].value, 'Font Name');
		}
	});
});
define([
	'intern!object',
	'intern/chai!assert',
	'xstyle/core/expression',
	'xstyle/core/base',
	'xstyle/core/Definition'
], function(registerSuite, assert, expression, base, Definition){
	var rule, obj, a, b, c;
	// TODO: should this go in Definition?
	function MutableDefinition(){
	}
	MutableDefinition.prototype = new Definition();
	MutableDefinition.prototype.put = MutableDefinition.prototype.setSource;

	registerSuite({
		name: 'expression',
		beforeEach: function(){
			rule = base.newRule();
			rule.parent = base;
			obj = {a: 1, b: 2, c: 3};
			a = new MutableDefinition();
			b = new MutableDefinition();
			c = new MutableDefinition();
			a.put(1);
			b.put(2);
			c.put(3);
			a = rule.declareDefinition('a', a);
			b = rule.declareDefinition('b', b);
			c = rule.declareDefinition('c', c);
		},
		'evaluate sum': function(){
			var aPlusB = expression.evaluate(rule, 'a + b');
			assert.equal(aPlusB.valueOf(), 3);
			var latestSum;
			aPlusB.observe(function(value){
				latestSum = value;
			});
			assert.equal(latestSum, 3);
			b.put(3);
			assert.equal(latestSum, 4);
			var latestA;
			a.observe(function(value){
				latestA = value;
			});
			aPlusB.put(9);
			assert.equal(latestA, 6);
			var threePlusB = expression.evaluate(rule, '5 + b');
			assert.equal(threePlusB.valueOf(), 8);
			var latestB;
			b.observe(function(value){
				latestB = value;
			});
			threePlusB.put(10);
			assert.equal(latestB, 5);
		},
		'evaluate multiply': function(){
			var aTimesB = expression.evaluate(rule, 'a*b');
			assert.equal(aTimesB.valueOf(), 2);
			var latestResult;
			aTimesB.observe(function(value){
				latestResult = value;
			});
			assert.equal(latestResult, 2);
			a.put(3);
			assert.equal(latestResult, 6);
			var latestA;
			a.observe(function(value){
				latestA = value;
			});
			aTimesB.put(8);
			assert.equal(latestA, 4);
		},
		'evaluate subtract': function(){
			var aMinusB = expression.evaluate(rule, 'a -b');
			assert.equal(aMinusB.valueOf(), -1);
			var latestResult;
			aMinusB.observe(function(value){
				latestResult = value;
			});
			assert.equal(latestResult, -1);
			a.put(5);
			assert.equal(latestResult, 3);
			var latestA;
			a.observe(function(value){
				latestA = value;
			});
			aMinusB.put(9);
			assert.equal(latestA, 11);
		},
		'evaluate precedence': function(){
			var result = expression.evaluate(rule, 'a+b*c');
			assert.equal(result.valueOf(), 7);
			var result = expression.evaluate(rule, 'a*b+c');
			assert.equal(result.valueOf(), 5);
			var latestA;
			a.observe(function(value){
				latestA = value;
			});
			result.put(11);
			assert.equal(latestA, 4);
		},
		'evaluate !': function(){
			var result = expression.evaluate(rule, '!a');
			assert.equal(result.valueOf(), false);
			var latestA;
			a.observe(function(value){
				latestA = value;
			});
			result.put(true);
			assert.equal(latestA, false);

		},
		'evaluate Math.min': function(){
			var minAB = expression.evaluate(rule, ['Math/min', {operator: '(', getArgs: function(){
				return ['a', 'b'];
			}}]);
			assert.equal(minAB.valueOf(), 1);
			var latestResult;
			minAB.observe(function(value){
				latestResult = value;
			});
			assert.equal(latestResult, 1);
			a.put(3);
			assert.equal(latestResult, 2);
			a.put(0);
			assert.equal(latestResult, 0);
		},
		'evaluate Math.sqrt': function(){
			var sqrtA = expression.evaluate(rule, ['Math/sqrt', {operator: '(', getArgs: function(){
				return ['a'];
			}}]);
			assert.equal(sqrtA.valueOf(), 1);
			var latestResult;
			sqrtA.observe(function(value){
				latestResult = value;
			});
			assert.equal(latestResult, 1);
			a.put(4);
			assert.equal(latestResult, 2);
			a.put(0);
			assert.equal(latestResult, 0);
		}

		/*,
		'evaluate groups': function(){
			a.put(5);
			var result = expression.evaluate(rule, 'a*(b+c)');
			assert.equal(result.valueOf(), 25);
			var latestA;
			a.observe(function(value){
				latestA = value;
			});
			result.put(50);
			assert.equal(latestA, 10);
		}*/
	});
});
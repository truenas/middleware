define(['dstore/Model', 'dstore/validators/NumericValidator'], function (Model, NumericValidator) {
	var model = new Model({
		firstName: 'John',
		lastName: 'Doe',
		age: 40,
		schema: {
			firstName: {
				label: 'First Name',
				type: 'string'
			},
			lastName: {
				label: 'Last Name',
				type: 'string'
			},
			age: new NumericValidator({
				label: 'Age',
				type: 'number',
				minimum: 0,
				maximum: 120
			}),

		}
	});
	return model;
});
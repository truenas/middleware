define(["dojo/store/Memory", "dojo/store/Observable"],function(Memory, Observable){
	var perfData = [], today = new Date().getTime();
	for(var i = 0; i < 20000; i++){
		perfData.push({
			id: i,
			integer: Math.floor(Math.random() * 100),
			floatNum: Math.random() * 100,
			date: new Date(today * Math.random() * 2),
			date2: new Date(today - Math.random() * 1000000000),
			text: "A number in text " + Math.random(),
			bool: Math.random() > 0.5,
			bool2: Math.random() > 0.5,
			price: Math.random() * 100,
			today: new Date(today)
		});
	}
	return Observable(new Memory({data: perfData}));
});
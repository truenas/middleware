define(['dstore/Memory', 'dstore/Trackable'], function(Memory, Trackable){
	// create an observable memory store with our test data 
	contactStore = new (Memory.createSubclass(Trackable))({data:[
		{id:1, firstName: 'Jimi', lastName:'Hendrix', email:'jimi@hendrix.com'},
		{id:2, firstName: 'Janis', lastName:'Joplin', email:'janis@fulltilt.com'},
		{id:3, firstName: 'Jim', lastName:'Morrison', email:'jm@thedoors.com'},	
		{id:4, firstName: 'Kurt', lastName:'Cobain', email:'cobain@nirvana.org'},
		{id:5, firstName: 'Amy', lastName:'Winehouse', email:'amy@wh.com'}
	]});
	var nextId = 6;
	// create a base binding, that we can set properties on
	contacts = {
		// list of contacts
		list: contactStore,
		select: function(item){
			contacts.selected = item;
		},
		save: function(selected){
			contactStore.put(selected);
		},
		create: newContact,
		'delete': function(selected){
			// delete
			contactStore.remove(selected.id);
			// and put a new object in the form, so the old one isn't there.
			newContact();
		}
	};
	// initialize with blank form
	newContact();
	function newContact(){
		contacts.selected = {firstName:'', lastName: '', email: '', id: nextId++};
	}

	return contacts;
});
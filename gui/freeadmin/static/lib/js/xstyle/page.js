define(['xstyle/core/base', 'xstyle/main', 'dojo/domReady!'], function(base){
	var contentText = document.getElementsByTagName('textarea')[0].value,
		body = document.body,
		entities = {
			'&lt;': '<',
			'&gt;': '>',
			'&amp;': '&'
		};
	
	body._contentNode = body;
	body.innerHTML = '';
	contentText = contentText.replace(/&\w+;/g, function(entity){
		return entities[entity];
	});
	// jshint evil: true
	var content = eval('(' + contentText + ')');
	base.definitions.pageContent.put(content);
});
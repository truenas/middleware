<%
	ups_config = middleware.call_sync('ups.config')

	driver = ups_config['driver'].split('$')[0]
	driver = driver.split('(')[0]  # "blazer_usb (USB ID 0665:5161)"
	driver = driver.split(' or ')[0]  # "blazer_ser or blazer_usb"
	driver = driver.replace(' ', '\n')  # "genericups upstype=16"
%>\
[${ups_config['identifier']}]
	driver = ${driver}
	port = ${ups_config['port']}
	desc = ${ups_config['description']}
	${ups_config['options']}

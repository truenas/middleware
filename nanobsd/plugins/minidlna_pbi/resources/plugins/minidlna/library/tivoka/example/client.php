<pre>
<?php
include('../include.php');

$target = 'http://'.$_SERVER['SERVER_NAME'].dirname($_SERVER['SCRIPT_NAME']).'/server.php';
$request = Tivoka::createRequest('1', 'demo.substract', array(43,1));
$greeting = Tivoka::createRequest('2', 'demo.sayHello');

Tivoka::connect($target)->send($request, $greeting);


/*
 * Display the Results...
 */

/*
 * Display reponse
 */
if($request->isError())
{
	// an error occured
	var_dump($request->error);
	var_dump($request->errorMessage);
	var_dump($request->reponse);
}
else var_dump($request->result);// the result

	
if($greeting->isError())
{
	// an error occured
	var_dump($greeting->error);
	var_dump($greeting->errorMessage);
	var_dump($greeting->response);
}
else var_dump($greeting->result);// the result

?>
</pre>
<?php
header("Content-Type: application/json");
$total = 500;
$id_prefix = "";
if(isset($_GET["parent"])){
	$id_prefix = $_GET["parent"]."-";
}
usleep(rand(0,500000));
$range = "";
if(isset($_SERVER["HTTP_RANGE"])){
	$range = $_SERVER["HTTP_RANGE"];
}else if(isset($_SERVER["HTTP_X_RANGE"])){
	$range = $_SERVER["HTTP_X_RANGE"];
}
if($range){
	preg_match('/(\d+)-(\d+)/', $range, $matches);
	
	$start = $matches[1];
	$end = $matches[2];
	if($end > $total){
		$end = $total;
	}
}else{
	$start = 0;
	$end = 40;
}
header('Content-Range: ' . 'items '.$start.'-'.$end.'/'.$total);
echo '[';
for ($i = $start; $i <= $end; $i++) {
	if($i != $start){
		echo ',';
	}
    echo '{"id":"'.$id_prefix.$i.'","name":"Item '.$i.'","comment":"hello"}';
}
echo ']';
?>

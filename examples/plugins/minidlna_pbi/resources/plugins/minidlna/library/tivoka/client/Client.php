<?php
/**
 * @package Tivoka
 * @author Marcel Klehr <mklehr@gmx.net>
 * @copyright (c) 2011, Marcel Klehr
 */
/**
 * JSON-RPC client
 * @package Tivoka
 */
class Tivoka_Client {
	
	/**
	 * Acts as a counter for the request IDs used
	 * @var integer
	 */
	public $id = 0;
	
	/**
	 * Holds the connection to the remote server
	 * @var Tivoka_Connection
	 */
	public $connection;
	
	/**
	 * Construct a native client
	 * @access private
	 * @param string $target URL
	 */
	public function __construct($target) {
		$this->connection = Tivoka::connect($target);
	}
	
	/**
	 * Sends a JSON-RPC request
	 * @param Tivoka_Request $request A Tivoka request
	 * @return void
	 */
	public function __call($method, $args) {
		$request = Tivoka::createRequest($this->id++, $method, $args);
		$this->connection->send($request);
		
		if($request->isError()) {
			throw new Tivoka_Exception($request->errorMessage, $request->error);
		}
		return $request->result;
	}

}
?>
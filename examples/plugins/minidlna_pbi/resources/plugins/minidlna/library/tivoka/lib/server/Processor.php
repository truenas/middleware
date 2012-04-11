<?php
/**
 * @package Tivoka
 * @author Marcel Klehr <mklehr@gmx.net>
 * @copyright (c) 2011, Marcel Klehr
 */
/**
 * Processes a single request on the server
 * @package Tivoka
 */
class Tivoka_Processor
{
	
	/**
	 * @var Tivoka_Server Reference to the parent server object for returning the result/error
	 * @access private
	 */
	public $server;
	
	/**
	 * @var array The parsed JSON-RPC request
	 * @see Tivoka_ServerProcessor::__construct()
	 */
	public $request;
	
	/**
	 * @var mixed The params as received through the JSON-RPC request
	 */
	public $params;
	
	/**
	 * Initializes a Tivoka_Processor object
	 * @param array $request The parsed JSON-RPC request
	 * @param Tivoka_Server $server The parent server object
	 */
	public function __construct(array $request, Tivoka_Server $server)
	{
		$this->server = $server;
		$this->request = array();
		$this->params = (isset($request['params']) === FALSE) ? null : $request['params'];
	
		//validate...
		if(($req = self::interpretRequest($request)) !== FALSE)
		{
			$this->request = $req;
		}
	
		if(($req = self::interpretNotification($request)) !== FALSE)
		{
			$this->request = $req;
		}
	
		if($this->request === array())
		{
			$this->error(-32600, $request);
			return;
		}
	
		//search method...
		if(!is_callable(array($this->server->host,$this->request['method'])))
		{
			$this->error(-32601);
			return;
		}
	
		//invoke...
		$this->server->host->{$this->request['method']}($this);
	}
	
	/**
	 * Receives the computed result
	 * @param mixed $result The computed result
	 */
	public function result($result)
	{
		if(self::interpretNotification($this->request) !== FALSE) return TRUE;
		$this->server->returnResult($this->request['id'],$result);
		return TRUE;
	}
	
	/**
	 * Receives the error from computing the result
	 *
	 * @param int $code The specified JSON-RPC error code
	 * @param mixed $data Additional data
	 */
	public function error($code, $message='', $data=null)
	{
		if(self::interpretNotification($this->request) !== FALSE) return FALSE;
		
		$id = (isset($this->request['id']) === FALSE) ? null : $this->request['id'];
		$this->server->returnError($id, $code, $message, $data);
		return FAlSE;
	}
	
	/**
	 * Validates and sanitizes a normal request
	 * @param array $assoc The json-parsed JSON-RPC request
	 * @static
	 * @return array Returns the sanitized request and if it was invalid, a boolean FALSE is returned
	 */
	public static function interpretRequest(array $assoc)
	{
		switch(Tivoka::$version) {
		case Tivoka::VER_2_0:
			if(isset($assoc['jsonrpc'], $assoc['id'], $assoc['method']) === FALSE) return FALSE;
			if($assoc['jsonrpc'] != '2.0' || !is_string($assoc['method'])) return FALSE;
			$request = array(
						'id' =>  &$assoc['id'],
						'method' => &$assoc['method']
			);
		if(isset($assoc['params'])) {
				if(!is_array($assoc['params'])) return FALSE;
				$request['params'] = $assoc['params'];
			}
			return $request;
		case Tivoka::VER_1_0:
			if(isset($assoc['id'], $assoc['method']) === FALSE) return FALSE;
			if(!is_string($assoc['method'])) return FALSE;
			$request = array(
									'id' =>  &$assoc['id'],
									'method' => &$assoc['method']
			);
			if(isset($assoc['params'])) {
				if((bool)count(array_filter(array_keys($assoc['params']), 'is_string'))) return FALSE;// if associative
				$request['params'] = &$assoc['params'];
			}
			return $request;
		}
	}
	
	/**
	 * Validates and sanitizes a notification
	 * @param array $assoc The json-parsed JSON-RPC request
	 * @static
	 * @return array Returns the sanitized request and if it was invalid, a boolean FALSE is returned
	 */
	public static function interpretNotification(array $assoc)
	{
		switch(Tivoka::$version) {
		case Tivoka::VER_2_0:
			if(isset($assoc['jsonrpc'], $assoc['method']) === FALSE || isset($assoc['id']) !== FALSE) return FALSE;
			if($assoc['jsonrpc'] != '2.0' || !is_string($assoc['method'])) return FALSE;
			$request = array(
				'method' => &$assoc['method']
			);
			if(isset($assoc['params'])) {
				if(!is_array($assoc['params'])) return FALSE;
				$request['params'] = $assoc['params'];
			}
			return $request;
		case Tivoka::VER_1_0:
			if(isset($assoc['method']) === FALSE || isset($assoc['id']) !== FALSE) return FALSE;
			if(!is_string($assoc['method'])) return FALSE;
			$request = array(
				'method' => &$assoc['method']
			);
			if(isset($assoc['params'])) {
				if((bool)count(array_filter(array_keys($assoc['params']), 'is_string'))) return FALSE;// if associative
				$request['params'] = $assoc['params'];
			}
			return $request;
		}
	}
}
?>
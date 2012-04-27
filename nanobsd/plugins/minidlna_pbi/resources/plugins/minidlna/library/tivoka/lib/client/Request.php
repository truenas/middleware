<?php
/**
 * @package Tivoka
 * @author Marcel Klehr <mklehr@gmx.net>
 * @copyright (c) 2011, Marcel Klehr
 */
/**
 * A JSON-RPC request
 * @package Tivoka
 */
class Tivoka_Request
{
	public $id;
	public $request;
	public $response;
	
	public $result;
	public $error;
	public $errorMessage;
	public $errorData;
	
	/**
	 * Constructs a new JSON-RPC request object
	 * @param mixed $id The id of the request
	 * @param string $method The remote procedure to invoke
	 * @param mixed $params Additional params for the remote procedure (optional)
	 * @see Tivoka_Connection::send()
	 */
	public function __construct($id,$method,$params=null) {
		$this->id = $id;
	
		//prepare...
		$this->request = self::prepareRequest($id, $method, $params);
	}
	
	/**
	 * Send this request to a remote server directly
	 * @param string $target The URL of the remote server
	 */
	public function send($target) {
		Tivoka::connect($target)->send($this);
	}
	
	/**
	* Interprets the response
	* @param string $response json data
	* @return void
	*/
	public function setResponse($response) {
		//process error?
		if($response === FALSE)
		{
			return;
		}
	
		$this->response = $response;
	
		//no response?
		if(trim($response) == '') {
			throw new Tivoka_Exception('No response received', Tivoka::ERR_NO_RESPONSE);
		}
	
		//decode
		$resparr = json_decode($response,true);
		if($resparr == NULL) {
			throw new Tivoka_Exception('Invalid response encoding', Tivoka::ERR_INVALID_JSON);
		}
		
		$this->interpretResponse($resparr);
	}
	
	/**
	 * Pack the request data with json encoding
	 * @return string the json encoded request
	 */
	public function __toString() {
		return json_encode($this->request);
	}
	
	/**
	* Interprets the parsed response
	* @param array $resparr
	*/
	public function interpretResponse($resparr) {
		//server error?
		if(($error = self::interpretError($resparr, $this->id)) !== FALSE) {
			$this->error        = $error['error']['code'];
			$this->errorMessage = $error['error']['message'];
			$this->errorData    = (isset($error['error']['data'])) ? $error['error']['data'] : null;
			return;
		}
	
		//valid result?
		if(($result = self::interpretResult($resparr, $this->id)) !== FALSE)
		{
			$this->result = $result['result'];
			return;
		}
	
		throw new Tivoka_Exception('Invalid response structure', Tivoka::ERR_INVALID_RESPONSE);
	}
	
	/**
	 * Determines whether an error occured
	 * @return bool
	 */
	public function isError()
	{
		return ($this->error != NULL);
	}
	
	/**
	 * Checks whether the given response is a valid result
	 * @param array $assoc The parsed JSON-RPC response as an associative array
	 * @param mixed $id The id of the original request
	 * @return array the parsed JSON object
	 */
	protected static function interpretResult(array $assoc, $id)
	{
		switch(Tivoka::$version) {
			case Tivoka::VER_2_0:
				if(isset($assoc['jsonrpc'], $assoc['result'], $assoc['id']) === FALSE) return FALSE;
				if($assoc['id'] !== $id || $assoc['jsonrpc'] != '2.0') return FALSE;
				return array(
						'id' => $assoc['id'],
						'result' => $assoc['result']
				);
			case Tivoka::VER_1_0:
				if(isset($assoc['result'], $assoc['id']) === FALSE) return FALSE;
				if($assoc['id'] !== $id && $assoc['result'] === null) return FALSE;
				return array(
					'id' => $assoc['id'],
					'result' => $assoc['result']
				);
		}
	}
	
	/**
	 * Checks whether the given response is valid and an error
	 * @param array $assoc The parsed JSON-RPC response as an associative array
	 * @param mixed $id The id of the original request
	 * @return array parsed JSON object
	 */
	protected static function interpretError(array $assoc, $id)
	{
		switch(Tivoka::$version) {
			case Tivoka::VER_2_0:
				if(isset($assoc['jsonrpc'], $assoc['error']) == FALSE) return FALSE;
				if($assoc['id'] != $id && $assoc['id'] != null && isset($assoc['id']) OR $assoc['jsonrpc'] != '2.0') return FALSE;
				if(isset($assoc['error']['message'], $assoc['error']['code']) === FALSE) return FALSE;
				return array(
						'id' => $assoc['id'],
						'error' => $assoc['error']
				);
			case Tivoka::VER_1_0:
				if(isset($assoc['error'], $assoc['id']) === FALSE) return FALSE;
				if($assoc['id'] != $id && $assoc['id'] !== null) return FALSE;
				if(isset($assoc['error']) === FALSE) return FALSE;
				return array(
					'id' => $assoc['id'],
					'error' => array('data' => $assoc['error'])
				);
		}
	}
	
	/**
	 * Encodes the request properties
	 * @param mixed $id The id of the request
	 * @param string $method The method to be called
	 * @param array $params Additional parameters
	 * @return mixed the prepared assotiative array to encode
	 */
	protected static function prepareRequest($id, $method, $params=null) {
		switch(Tivoka::$version) {
		case Tivoka::VER_2_0:
			$request = array(
					'jsonrpc' => '2.0',
					'method' => $method,
			);
			if($id !== null) $request['id'] = $id;
			if($params !== null) $request['params'] = $params;
			return $request;
		case Tivoka::VER_1_0:
			$request = array(
				'method' => $method,
				'id' => $id
			);
			if($params !== null) {
				if((bool)count(array_filter(array_keys($params), 'is_string'))) throw new Tivoka_Exception('JSON-RC 1.0 doesn\'t allow for named parameters');
				$request['params'] = $params;
			}
			return $request;
		}
	}
}
?>

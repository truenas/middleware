<?php
/**
 * @package Tivoka
 * @author Marcel Klehr <mklehr@gmx.net>
 * @copyright (c) 2011, Marcel Klehr
 */
/**
 * Processes the  JSON-RPC input
 * @package Tivoka
 */
class Tivoka_Server
{
	/**
	* @var object The object given to __construct()
	* @see Tivoka_Server::__construct()
	* @access private
	*/
	public $host;
	
	/**
	 * @var array The parsed json input as an associative array
	 * @access private
	 */
	private $input;
	
	/**
	 * @var array A list of associative response arrays to json_encode
	 * @access private
	 */
	private $response;
	
	/**
	 * Constructss a Server object
	 * @param object $host An object whose methods will be provided for invokation
	 * @param bool $hide_errors Pass TRUE for hiding all eventual erros to avoid messing up the response
	 */
	public function __construct($host, $hide_errors=0) {
		// disable error reporting?
		if($hide_errors == Tivoka::HIDE_ERRORS) error_reporting(0);// avoids messing up the response
		
		if(is_array($host)) {
			$host = new Tivoka_MethodWrapper($host);
		}
		
		$this->host = $host;
		$this->input = file_get_contents('php://input');
		$json_errors = array(
			JSON_ERROR_NONE => '',
			JSON_ERROR_DEPTH => 'The maximum stack depth has been exceeded',
			JSON_ERROR_CTRL_CHAR => 'Control character error, possibly incorrectly encoded',
			JSON_ERROR_SYNTAX => 'Syntax error'
		);
		
		// set header if not already sent...
		if(headers_sent() === FALSE) header('Content-type: application/json');
		
		
		// any request at all?
		if(trim($this->input) === '')
		{
			$this->returnError(null,-32600);
			$this->respond();
		}
		
		// decode request...
		$this->input = json_decode($this->input,true);
		if($this->input === NULL)
		{
			$this->returnError(null,-32700, 'JSON parse error: '.$json_errors[json_last_error()] );
			$this->respond();
		}
		
		// batch?
		if(($batch = self::interpretBatch($this->input)) !== FALSE)
		{
			foreach($batch as $request)
			{
				$this->process($request);
			}
			$this->respond();
		}
		
		//process request
		$this->process($this->input);
		$this->respond();
	}
	
	/**
	 * Starts processing of the passed request
	 * @param array $request the parsed request
	 */
	public function process($request) {
		new Tivoka_Processor($request, $this);
	}
	
	/**
	 * Receives the computed result
	 * @param mixed $id The id of the original request
	 * @param mixed $result The computed result
	 * @access private
	 */
	public function returnResult($id,$result)
	{
		switch(Tivoka::$version) {
		case Tivoka::VER_2_0:
			$this->response[] = array(
						'jsonrpc' => '2.0',
						'id' => $id,
						'result' => $result
			);
			break;
		case Tivoka::VER_1_0:
			$this->response[] = array(
								'id' => $id,
								'result' => $result,
								'error' => null
			);
			break;
		}
	}
	
	/**
	 * Receives the error from computing the result
	 * @param mixed $id The id of the original request
	 * @param integer $code The error code
	 * @param string $message The error message
	 * @param mixed $data Additional data
	 * @access private
	 */
	public function returnError($id, $code, $message='', $data=null)
	{
		$msg = array(
			-32700 => 'Parse error',
			-32600 => 'Invalid Request',
			-32601 => 'Method not found',
			-32602 => 'Invalid params',
			-32603 => 'Internal error'
		);
		switch(Tivoka::$version) {
		case Tivoka::VER_2_0:
			$response = array(
				'jsonrpc'=>'2.0',
				'id'=>$id,
				'error'=> array(
					'code'=>$code,
					'message'=>$message,
					'data'=>$data
			));
			break;
		case Tivoka::VER_1_0:
			$response = array(
				'id'=>$id,
				'result' => null,
				'error'=> array(
					'code'=>$code,
					'message'=>$message,
					'data'=>$data
			));
			break;
		}
		if($message === '')$response['error']['message'] = $msg[$code];
		$this->response[] = $response;
	}
	
	/**
	* Outputs the processed response
	* @access private
	*/
	public function respond()
	{
		if(!is_array($this->response))//no array
			exit;
		
		$count = count($this->response);
		
		if($count == 1)//single request
			die(json_encode($this->response[0]));
	
		if($count > 1)//batch request
			die(json_encode($this->response));
	
		if($count < 1)//no response
			exit;
	}
	
	/**
	* Validates a batch request
	* @param array $assoc The json-parsed JSON-RPC request
	* @static
	* @return array Returns the original request and if it was invalid, a boolean FALSE is returned
	* @access private
	*/
	public static function interpretBatch(array $assoc)
	{
		if(count($assoc) <= 1)
		return FALSE;
	
		foreach($assoc as $req)
		{
			if(!is_array($req))
				return FALSE;
		}
		return $assoc;
	}
}
?>
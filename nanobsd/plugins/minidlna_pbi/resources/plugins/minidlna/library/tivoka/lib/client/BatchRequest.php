<?php
/**
 * @package Tivoka
 * @author Marcel Klehr <mklehr@gmx.net>
 * @copyright (c) 2011, Marcel Klehr
 */
/**
 * A batch request
 * @package Tivoka
 */
class Tivoka_BatchRequest extends Tivoka_Request
{
	/**
	 * Constructs a new JSON-RPC batch request
	 * All values of type other than Tivoka_Request will be ignored
	 * @param array $batch A list of requests to include, each a Tivoka_Request
	 * @see Tivoka_Client::send()
	 */
	public function __construct(array $batch)
	{
		if(Tivoka::$version == Tivoka::VER_1_0) throw new Tivoka_exception('Batch requests are not supported by JSON-RPC 1.0 spec', Tivoka::ERR_SPEC_INCOMPATIBLE);
		$this->id = array();
	
		//prepare requests...
		foreach($batch as $request)
		{
			if(!($request instanceof Tivoka_Request) && !($request instanceof Tivoka_Notification))
				continue;
			
			//request...
			if($request instanceof Tivoka_Request)
			{
				if(in_array($request->id,$this->id,true)) continue;
				$this->id[$request->id] = $request;
			}
			
			$this->request[] = $request->request;
		}
	}
	
	/**
	* Interprets the parsed response
	* @param array $resparr json data
	* @return void
	*/
	public function interpretResponse($resparr) {
		//validate
		if(count($resparr) < 1 || !is_array($resparr)) {
			throw new Tivoka_Exception('Expected batch response, but none was received', Tivoka::ERR_INVALID_RESPONSE);
		}
	
		$requests = $this->id;
		$nullresps = array();
		$responses = array();
	
		//split..
		foreach($resparr as $resp)
		{
			if(!is_array($resp)) throw new Tivoka_Exception('Expected batch response, but no array was received', Tivoka::ERR_INVALID_RESPONSE);
				
			//is jsonrpc protocol?
			if(!isset($resp['jsonrpc']) && !isset($resp['id'])) throw new Tivoka_Exception('The received reponse doesn\'t implement the JSON-RPC prototcol.', Tivoka::ERR_INVALID_RESPONSE);
				
			//responds to an existing request?
			if(!array_key_exists($resp['id'], $requests))
			{
				if($resp['id'] != null) continue;
	
				$nullresps[] = $resp;
				continue;
			}
	
			//normal response...
			$requests[ $resp['id'] ]->setResponse(json_encode($resp));
			unset($requests[ $resp['id'] ]);
		}
	
		//handle id:null responses...
		foreach($requests as $req)
		{
			$resp = array_shift($nullresps);
			$requests[ $req->id ]->setResponse(json_encode($resp));
		}
	}
}
?>
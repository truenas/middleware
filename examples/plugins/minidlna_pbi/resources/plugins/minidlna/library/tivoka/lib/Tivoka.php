<?php
/**
 * @package Tivoka
 * @author Marcel Klehr <mklehr@gmx.net>
 * @copyright (c) 2011, Marcel Klehr
 */
/**
 * The public interface to all tivoka functions
 * @package Tivoka
 */
abstract class Tivoka
{
	const ERR_NO_RESPONSE = 1;      // 000 000 001
	const ERR_INVALID_JSON = 2;     // 000 000 010
	const ERR_INVALID_RESPONSE = 3; // 000 000 011
	const ERR_CONNECTION_FAILED = 4;// 000 000 100
	const ERR_SPEC_INCOMPATIBLE = 5;// 000 000 101
	
	const ERR_INVALID_TARGET = 6;   // 000 000 110
	const HIDE_ERRORS = 7;          // 000 000 111
	
	const VER_1_0 = 8;              // 000 001 000
	const VER_2_0 = 16;             // 000 010 000
	
	public static $version = Tivoka::VER_2_0;
	
	
	/**
	 * Initializes a Connection to a remote server
	 * @param string $target the URL of the target server (MUST include http scheme)
	 * @throws Tivoka_Exception
	 * @return Tivoka_Connection
	 */
	public static function connect($target) {
		//validate url...
		if(!filter_var($target, FILTER_VALIDATE_URL, FILTER_FLAG_SCHEME_REQUIRED))
		throw new Tivoka_Exception('Valid URL (scheme://domain[/path][/file]) required.', Tivoka::ERR_INVALID_TARGET);
		
		//validate scheme...
		$t = parse_url($target);
		if($t['scheme'] !== 'http')
		throw new Tivoka_Exception('Unknown or unsupported scheme given.', Tivoka::ERR_INVALID_TARGET);
		
		return new Tivoka_Connection($target);
	}
	
	/**
	 * Creates a request
	 * @throws Tivoka_Exception
	 * @param mixed $id The id of the request
	 * @param string $method The method to invoke
	 * @param array $params The parameters
	 * @return Tivoka_Request
	 */
	public static function createRequest($id, $method, $params=null) {
		return new Tivoka_Request($id, $method, $params);
	}
	
	/**
	 * Creates a notification
	 * @throws Tivoka_Exception
	 * @param string $method The method to invoke
	 * @param array $params The parameters
	 */
	public static function createNotification($method, $params=null) {
		return new Tivoka_Notification($method, $params);
	}
	
	/**
	 * Creates a batch request
	 * @param mixed $request either an array of requests or a comma-seperated list of requests
	 * @throws Tivoka_Exception
	 * @return Tivoka_BatchRequest
	 */
	public static function createBatch($request) {
		if(func_num_args() > 1 ) $request = func_get_args();
		if(is_array($request)) {
			return new Tivoka_BatchRequest($request);
		}
		throw new Tivoka_Exception('Object of invalid data type passed to Tivoka::createBatch.');
	}
	
	/**
	 * Starts processing the HTTP input
	 * Notice: Calling this method will stop further execution of the script!
	 * @param object $host An object whose methods will be provided for invokation
	 * @param integer $hide_errors Optionally pass `Tivoka::HIDE_ERRORS` to hide all errors from the output
	 * @return Tivoka_Server
	 */
	static function createServer($host, $hide_errors=0)
	{
		return new Tivoka_Server($host);
	}
	
	/**
	 * Creates a native remote interface to the methods provided by the target server
	 * @param string $target the URL of the target server (MUST include http scheme)
	 * @return Tivoka_Client
	 */
	static function createClient($target)
	{
		return new Tivoka_Client($target);
	}
}
?>
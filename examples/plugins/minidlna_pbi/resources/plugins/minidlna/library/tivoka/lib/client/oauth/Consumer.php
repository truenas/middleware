<?php
/**
 * @package Tivoka
 * @author William Grzybowski <william88@gmail.com>
 */
/**
 * JSON-RPC client
 * @package Tivoka
 */

class OAuth_Consumer {

	public $key;
	public $secret;

	function __construct($key, $secret) {
		$this->key = $key;
		$this->secret = $secret;

		if(!$this->key or !$this->secret) {
			throw new Exception('Key and secret must be set.');
		}
	}

	function __toString() {
		return http_build_query(array(
			'oauth_consumer_key' => $this->key,
			'oauth_consumer_secret' => $this->secret
			));
	}

}

?>

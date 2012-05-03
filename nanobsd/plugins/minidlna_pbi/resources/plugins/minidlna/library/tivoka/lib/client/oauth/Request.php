<?php

class OAuth_Request {

	public $oauth_params;
	public $url;

	function __construct($consumer, $method, $url, $params, $body) {

		$this->url = $url;
		$this->oauth_params = array(
			'oauth_version' => '1.0',
			'oauth_nonce' => '94078240',
			'oauth_consumer_key' => $consumer->key,
			'oauth_timestamp' => time(),
			'oauth_body_hash' => base64_encode(hash('sha1', $body, TRUE)),
			'oauth_signature_method' => 'HMAC-SHA1',
		);

		ksort($this->oauth_params);
		$query = http_build_query($this->oauth_params);

		$raw = array(
			$method,
			urlencode($url),
			urlencode($query),
		);

		$raw_hmac = hash_hmac('sha1', implode('&', $raw), $consumer->secret.'&', true);
		$this->oauth_params['oauth_signature'] = base64_encode($raw_hmac);

	}

	public function request($context) {
		return @file_get_contents($this->url.'?'.http_build_query($this->oauth_params), false, $context);

	}

}
?>

<?php

class FreeNAS_Lib_MiniDLNA {

    public $ARCH = null;
    public $BASE = null;
    public $CONF = null;
    public $RCOPTIONS = array(
        'port' => array(
            'opt' => '-d',
            ),
    );
    const CONTROL = "/usr/local/etc/rc.d/minidlna";

    function __construct() {

        $this->ARCH = shell_exec('/usr/bin/uname -m');
        $this->BASE = "/usr/pbi/minidlna-" . $this->ARCH;
        $this->CONF = $this->BASE . "/etc/minidlna.conf";
        $this->RCCONF = $this->BASE . "/etc/rc.conf";

    }

    public function writeConf($obj) {

        $fp = fopen($this->RCCONF, "w");
        fwrite($fp, sprintf("%s %s", '-d', $obj->getId());
        fclose($fp);

    }

}

?>

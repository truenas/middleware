<?php

class FreenasController extends Zend_Controller_Action
{

    public function init()
    {
	    $this->_helper->viewRenderer->setNoRender(TRUE);
    }

    public function treemenuAction()
    {
        echo json_encode(array(
            array(
                'name' => 'MiniDLNA',
                'append_to' => 'services.PluginsJail',
                'type' => 'pluginsfcgi',
                'url' => '/plugins/minidlna/edit',
            ),
        ));
    }

    public function startAction()
    {

    }

    public function stopAction()
    {

    }

    public function statusAction()
    {

    }

}


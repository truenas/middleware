<?php

class FreenasController extends Zend_Controller_Action
{

    public function init()
    {
        $this->_helper->viewRenderer->setNoRender(TRUE);
        $this->getResponse()->setHeader('Content-type', 'application/json');
        $session = $this->getRequest()->getCookie('sessionid');
        $this->lib = new FreeNAS_Lib_MiniDLNA();
        $this->lib->isAuthorized($session);
    }

    public function treemenuAction()
    {
        echo json_encode(array(
            array(
                'name' => 'MiniDLNA',
                'append_to' => 'plugins',
                'type' => 'pluginsfcgi',
                'icon' => '/plugins/minidlna/' . $this->getParam("plugin_id") . '/index/treemenuicon',
                'url' => '/plugins/minidlna/' . $this->getParam("plugin_id") . '/index/edit',
            ),
        ));
    }

    public function startAction()
    {

        echo json_encode(
            $this->lib->start()
        );

    }

    public function stopAction()
    {

        echo json_encode(
            $this->lib->stop()
        );

    }

    public function statusAction()
    {

        echo json_encode(
            $this->lib->status()
        );

    }

}

?>

<?php

class FreenasController extends Zend_Controller_Action
{

    public function init()
    {
        $this->_helper->viewRenderer->setNoRender(TRUE);
        $this->getResponse()->setHeader('Content-type', 'application/json');
        $session = $this->getRequest()->getCookie('sessionid');
        $lib = new FreeNAS_Lib_MiniDLNA();
        $lib->isAuthorized($session);
    }

    public function treemenuAction()
    {
        echo json_encode(array(
            array(
                'name' => 'MiniDLNA',
                'append_to' => 'services.PluginsJail',
                'type' => 'pluginsfcgi',
                'icon' => 'SettingsIcon',
                'url' => '/plugins/minidlna/index/edit',
            ),
        ));
    }

    public function startAction()
    {

        $lib = new FreeNAS_Lib_MiniDLNA();
        echo json_encode(
            $lib->start()
        );

    }

    public function stopAction()
    {

        $lib = new FreeNAS_Lib_MiniDLNA();
        echo json_encode(
            $lib->stop()
        );

    }

    public function statusAction()
    {

        $lib = new FreeNAS_Lib_MiniDLNA();
        echo json_encode(
            $lib->status()
        );

    }

}


<?php

class Bootstrap extends Zend_Application_Bootstrap_Bootstrap
{

    protected function _initAutoload()
    {

        $autoLoader = Zend_Loader_Autoloader::getInstance();
        //$autoLoader->setFallbackAutoloader(true);

        $autoloader = new Zend_Application_Module_Autoloader(array(
                'namespace' => 'FreeNAS_',
                'basePath'  => APPLICATION_PATH . '/',
                'resourceTypes' => array(
                    'forms' => array(
                        'path' => '/forms',
                        'namespace' => 'Form')
                )
            )
        );

    }

}


<?php

class IndexController extends Zend_Controller_Action
{

    public function init()
    {
        Zend_Dojo_View_Helper_Dojo::setUseDeclarative();
        $this->view->addHelperPath('Zend/Dojo/View/Helper/', 'Zend_Dojo_View_Helper');
    }

    public function indexAction()
    {
    }

    public function editAction()
    {
        $form = new FreeNAS_Form_Edit;
        $this->view->form = $form;
    }


}


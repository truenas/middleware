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

        $em = Zend_Registry::get('em');
        $minidlna = $em->getRepository('Entity\MiniDLNA')->findAll();
        if(count($minidlna) != 0) {
            $minidlna = $minidlna[0];
            //$em->persist($paul);
            //$em->flush();
        } else {
            $minidlna = new Entity\MiniDLNA();
        }

        $form = new FreeNAS_Form_Edit;
        $form->enabled->setValue(1);
        $this->view->form = $form;
    }


}


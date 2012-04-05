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

        if($this->getRequest()->isPost()) {

            $this->_helper->viewRenderer->setNoRender(TRUE);
            $this->getResponse()->setHeader('Content-type', 'application/json');

            if($form->isValid($_POST)) {
                echo json_encode(
                    array(
                        'error' => false,
                        'message' => 'Settings successfully updated',
                    )
                );
            } else {

                $data =    array(
                        'error' => true,
                        'type' => 'form',
                        'formid' => $_POST['__form_id'],
                    );
                $errors = array();
                foreach($form->getMessages() as $field => $val) {
                    $errors[$field] = array();
                    foreach($val as $error => $msg) {
                        $errors[$field][] = $msg;
                    }
                }
                $data['errors'] = $errors;
                echo json_encode($data);
            }

        } else {
            $form->enabled->setValue($minidlna->getEnabled());
            $this->view->form = $form;
        }
    }


}


<?php

class IndexController extends Zend_Controller_Action
{

    public $lib;

    public function init()
    {
        Zend_Dojo_View_Helper_Dojo::setUseDeclarative();
        $this->view->addHelperPath('Zend/Dojo/View/Helper/', 'Zend_Dojo_View_Helper');
        $session = $this->getRequest()->getCookie('sessionid');
        $this->lib = new FreeNAS_Lib_MiniDLNA();
        $this->lib->isAuthorized($session);
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
        } else {
            $minidlna = new Entity\MiniDLNA();
        }

        $form = new FreeNAS_Form_Edit;
        $jail = Tivoka::createRequest('1', 'plugins.jail.info');
        $this->lib->getRpc()->send($jail);
        $jail = json_decode($jail->result);
        $form->media_dir->setAttrib('root', $jail[0]->fields->jail_path . '/' . $jail[0]->fields->jail_name);

        if($this->getRequest()->isPost()) {

            $this->_helper->viewRenderer->setNoRender(TRUE);
            $this->getResponse()->setHeader('Content-type', 'application/json');

            if($form->isValid($_POST)) {
                //foreach($form->getValues() as $field => $value) {

                //}
                $values = $form->getValues();
                $minidlna->setEnabled($values['enabled']);
                $minidlna->setMediaDir($values['media_dir']);
                if(isset($values['inotify']))
                    $minidlna->setInotify($values['inotify']);
                $minidlna->setNotifyInterval($values['notify_interval']);
                $minidlna->setFriendlyName($values['friendly_name']);
                if(isset($values['tivo']))
                    $minidlna->setTivo($values['tivo']);
                $minidlna->setRescan($values['rescan']);
                $em->persist($minidlna);
                $em->flush();

                $lib = new FreeNAS_Lib_MiniDLNA();
                $lib->writeConf($minidlna);

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
            $form->media_dir->setValue($minidlna->getMediaDir());
            $form->port->setValue($minidlna->getPort());
            $form->inotify->setValue($minidlna->getInotify());
            $form->notify_interval->setValue($minidlna->getNotifyInterval());
            $form->friendly_name->setValue($minidlna->getFriendlyName());
            $form->tivo->setValue($minidlna->getTivo());
            $form->rescan->setValue($minidlna->getRescan());
            $this->view->form = $form;
        }
    }


}


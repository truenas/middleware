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
        /*
         * We need to make sure the user viewing this is logged in the FreeNAS GUI
         * Pass the sessionid via JSON-RPC and make sure it has access
         */
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

                $values = $form->getValues();
                $minidlna->setMediaDir($values['media_dir']);
                if(isset($values['inotify']))
                    $minidlna->setInotify($values['inotify']);
                $minidlna->setNotifyInterval($values['notify_interval']);
                $minidlna->setFriendlyName($values['friendly_name']);
                if(isset($values['tivo']))
                    $minidlna->setTivo($values['tivo']);
                $minidlna->setRescan($values['rescan']);
                $minidlna->setStrictDLNA($values['strict_dlna']);
                $minidlna->setModelNumber($values['model_number']);
                $minidlna->setSerial($values['serial']);
                $minidlna->setAuxiliary($values['auxiliary']);
                $em->persist($minidlna);
                $em->flush();

                $this->lib->writeConf($minidlna);

                echo json_encode(
                    array(
                        'error' => false,
                        'message' => 'Settings successfully updated',
                    )
                );

            } else {

                /*
                 * This is an internal API of the FreeNAS GUI
                 *
                 * The JSON returned in case of form validation error must
                 * return the following object:
                 * {
                 * 'error': true,
                 * 'type': 'form',
                 * 'formid': 'formid', // Id of the dijit form
                 * 'errors': {   // Array of errors with fieldnames as keys
                 *  'fieldname': ['error 1', 'error 2'],
                 *   }
                 * }
                 */
                $data = array(
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

            $form->media_dir->setValue($minidlna->getMediaDir());
            $form->port->setValue($minidlna->getPort());
            $form->inotify->setValue($minidlna->getInotify());
            $form->notify_interval->setValue($minidlna->getNotifyInterval());
            $form->friendly_name->setValue($minidlna->getFriendlyName());
            $form->tivo->setValue($minidlna->getTivo());
            $form->strict_dlna->setValue($minidlna->getStrictDLNA());
            $form->model_number->setValue($minidlna->getModelNumber());
            $form->serial->setValue($minidlna->getSerial());
            $form->auxiliary->setValue($minidlna->getAuxiliary());
            $form->rescan->setValue($minidlna->getRescan());
            $this->view->form = $form;

        }
    }

    public function treemenuiconAction()
    {
        $this->_helper->viewRenderer->setNoRender(TRUE);
        $this->getResponse()->setHeader('Content-type', 'image/png');
        echo $this->lib->getIcon();
    }

}
?>

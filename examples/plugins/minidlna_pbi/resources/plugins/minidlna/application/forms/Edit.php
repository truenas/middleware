<?php
class FreeNAS_Form_Edit extends Zend_Dojo_Form
{

    public function init()
    {

        $this->setMethod('post');
        $this->setAttribs(array(
            'name'  => 'masterForm',
        ));
        $this->setDecorators(array(
            'FormElements',
        ));
        $this->setElementDecorators(array(
            'DijitElement',
            'Errors',
            array(array('data' => 'HtmlTag'), array('tag' => 'td')),
            array('Label', array('tag' => 'td')),
            array(array('row' => 'HtmlTag'), array('tag' => 'tr'))
        ));

        $decs = array(
            'ViewHelper',
            'Errors',
            array(array('data' => 'HtmlTag'), array('tag' => 'td')),
            array('Label', array('tag' => 'td')),
            array(array('row' => 'HtmlTag'), array('tag' => 'tr'))
            );

        $media_dir = new Zend_Form_Element_Text(array(
            'name' => 'media_dir',
            'label' => 'Media directory',
            'required' => true,
            'dojoType' => 'freeadmin.form.PathSelector')
            );
        $media_dir->setDecorators($decs);

        $inotify = new Zend_Form_Element_Checkbox(array(
            'name' => 'inotify',
            'label' => 'Automatic discover',
            'dojoType' => 'dijit.form.CheckBox')
            );
        $inotify->setDecorators($decs);

        $enabled = new Zend_Form_Element_Checkbox(array(
            'name' => 'enabled',
            'label' => 'Enabled',
            'dojoType' => 'dijit.form.CheckBox')
            );
        $enabled->setDecorators($decs);

        $tivo = new Zend_Form_Element_Checkbox(array(
            'name' => 'tivo',
            'label' => 'Enable TiVo',
            'dojoType' => 'dijit.form.CheckBox')
            );
        $tivo->setDecorators($decs);

        $friendly_name = new Zend_Form_Element_Text(array(
            'name' => 'friendly_name',
            'label' => 'Friendly name',
            'dojoType' => 'dijit.form.TextBox')
            );
        $friendly_name->setDecorators($decs);

        $rescan = new Zend_Form_Element_Checkbox(array(
            'name' => 'rescan',
            'label' => 'Rescan on (re)start',
            'dojoType' => 'dijit.form.CheckBox')
            );
        $rescan->setDecorators($decs);

        $this->addElement($enabled)
             ->addElement($friendly_name)
             ->addElement($media_dir)
             ->addElement(
                 'NumberTextBox',
                 'port',
                 array(
                     'label'      => 'Port',
                     'required' => true,
                     'allowEmpty' => false,
                 )
             )
             ->addElement($inotify)
             ->addElement(
                 'TextBox',
                 'notify_interval',
                 array(
                     'label'      => 'Discover interval (seconds)',
                     'required' => true,
                     'allowEmpty' => false,
                 )
             )
             ->addElement($tivo)
             ->addElement($rescan)
             ;

    }
}
?>

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

        $this->addElement($enabled)
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
             ;

    }
}
?>

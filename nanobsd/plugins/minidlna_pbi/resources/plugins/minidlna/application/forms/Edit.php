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
            array('Label', array('tag' => 'th')),
            array(array('row' => 'HtmlTag'), array('tag' => 'tr'))
        ));

        $decs = array(
            'ViewHelper',
            'Errors',
            array(array('data' => 'HtmlTag'), array('tag' => 'td')),
            array('Label', array('tag' => 'th')),
            array(array('row' => 'HtmlTag'), array('tag' => 'tr'))
            );

        $media_dir = new Zend_Form_Element_Text(array(
            'name' => 'media_dir',
            'label' => 'Media directory',
            'required' => true,
            'dojoType' => 'freeadmin.form.PathSelector')
            );
        $media_dir->setDecorators($decs);

        //$inotify = new Zend_Form_Element_Checkbox(array(
        $inotify = new Zend_Form_Element_Hidden(array(
            'name' => 'inotify',
            'label' => 'Automatic discover',
            //'dojoType' => 'dijit.form.CheckBox',
            ));
        //$inotify->setDecorators($decs);
        $inotify->setDecorators(array('ViewHelper'));

        //$enabled = new Zend_Form_Element_Checkbox(array(
        //    'name' => 'enabled',
        //    'label' => 'Enabled',
        //    'dojoType' => 'dijit.form.CheckBox')
        //    );
        //$enabled->setDecorators($decs);

        //$tivo = new Zend_Form_Element_Checkbox(array(
        $tivo = new Zend_Form_Element_Hidden(array(
            'name' => 'tivo',
            'label' => 'Enable TiVo',
            //'dojoType' => 'dijit.form.CheckBox'
            ));
        //$tivo->setDecorators($decs);
        $tivo->setDecorators(array('ViewHelper'));

        $friendly_name = new Zend_Form_Element_Text(array(
            'name' => 'friendly_name',
            'label' => 'Friendly name',
            'dojoType' => 'dijit.form.TextBox')
            );
        $friendly_name->setDecorators($decs);

        $model_number = new Zend_Form_Element_Text(array(
            'name' => 'model_number',
            'label' => 'Model number',
            'dojoType' => 'dijit.form.TextBox')
            );
        $model_number->setDecorators($decs);

        $serial = new Zend_Form_Element_Text(array(
            'name' => 'serial',
            'label' => 'Serial',
            'dojoType' => 'dijit.form.TextBox')
            );
        $serial->setDecorators($decs);

        $auxiliary = new Zend_Form_Element_Text(array(
            'name' => 'auxiliary',
            'label' => 'Auxiliary parameters',
            'dojoType' => 'dijit.form.Textarea')
            );
        $auxiliary->setDecorators($decs);

        $rescan = new Zend_Form_Element_Checkbox(array(
            'name' => 'rescan',
            'label' => 'Rescan on (re)start',
            'dojoType' => 'dijit.form.CheckBox')
            );
        $rescan->setDecorators($decs);

        $strict_dlna = new Zend_Form_Element_Checkbox(array(
            'name' => 'strict_dlna',
            'label' => 'Strict DLNA',
            'dojoType' => 'dijit.form.CheckBox')
            );
        $strict_dlna->setDecorators($decs);

        $this->addElement($friendly_name)
             //->addElement($enabled)
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
             ->addElement($strict_dlna)
             ->addElement($model_number)
             ->addElement($serial)
             ->addElement($rescan)
             ->addElement($auxiliary)
             ;

    }
}
?>

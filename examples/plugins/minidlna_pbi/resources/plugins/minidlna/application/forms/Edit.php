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

        $media_dir = new Zend_Form_Element_Text(array(
            'name' => 'media_dir',
            'label' => 'Media Directory',
            'required' => true,
            'dojoType' => 'freeadmin.form.PathSelector')
            );
        $media_dir->setDecorators(array(
            'ViewHelper',
            'Errors',
            array(array('data' => 'HtmlTag'), array('tag' => 'td')),
            array('Label', array('tag' => 'td')),
            array(array('row' => 'HtmlTag'), array('tag' => 'tr'))
            ));

        $this->addElement(
                'CheckBox',
                'enabled',
                array(
                    'label'      => 'Enabled',
                    'required' => false,
                    'allowEmpty' => true,
                )
            )
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
            ;

    }
}
?>

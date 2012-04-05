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

        $this->addElement(
                'CheckBox',
                'enabled',
                array(
                    'label'      => 'Enabled',
                    'required' => false,
                    'allowEmpty' => true,
                )
            )
            ->addElement(
                'DateTextBox',
                'datebox',
                array(
                    'value'     => '2008-07-05',
                    'label'     => 'DateTextBox',
                    'required'  => true,
                )
            )
            ;

    }
}
?>

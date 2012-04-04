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
            'DijitForm',
        ));
        $textForm = new Zend_Dojo_Form_SubForm();
        $textForm->setAttribs(array(
            'name'   => 'textboxtab',
            'legend' => 'Text Elements',
            'dijitParams' => array(
                'title' => 'Text Elements',
            ),
        ));
        $textForm->addElement(
                'TextBox',
                'textbox',
                array(
                    'value'      => 'some text',
                    'label'      => 'TextBox',
                    'trim'       => true,
                    'propercase' => true,
                )
            )
            ->addElement(
                'DateTextBox',
                'datebox',
                array(
                    'value' => '2008-07-05',
                    'label' => 'DateTextBox',
                    'required'  => true,
                )
            )
            ->addElement(
                'TimeTextBox',
                'timebox',
                array(
                    'label' => 'TimeTextBox',
                    'required'  => true,
                )
            )
            ->addElement(
                'CurrencyTextBox',
                'currencybox',
                array(
                    'label' => 'CurrencyTextBox',
                    'required'  => true,
                    // 'currency' => 'USD',
                    'invalidMessage' => 'Invalid amount. ' .
                                        'Include dollar sign, commas, ' .
                                        'and cents.',
                    // 'fractional' => true,
                    // 'symbol' => 'USD',
                    // 'type' => 'currency',
                )
            )
            ->addElement(
                'NumberTextBox',
                'numberbox',
                array(
                    'label' => 'NumberTextBox',
                    'required'  => true,
                    'invalidMessage' => 'Invalid elevation.',
                    'constraints' => array(
                        'min' => -20000,
                        'max' => 20000,
                        'places' => 0,
                    )
                )
            )
            ->addElement(
                'ValidationTextBox',
                'validationbox',
                array(
                    'label' => 'ValidationTextBox',
                    'required'  => true,
                    'regExp' => '[\w]+',
                    'invalidMessage' => 'Invalid non-space text.',
                )
            )
            ->addElement(
                'Textarea',
                'textarea',
                array(
                    'label'    => 'Textarea',
                    'required' => true,
                    'style'    => 'width: 200px;',
                )
            );

        $this->addSubForm($textForm, 'textboxtab');

    }
}
?>

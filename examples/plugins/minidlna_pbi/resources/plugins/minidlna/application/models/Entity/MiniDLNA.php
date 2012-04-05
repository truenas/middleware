<?php

namespace Entity;

use Doctrine\Common\Collections\ArrayCollection;

/**
 * @Entity
 * @Table(name="minidlna")
 */
class MiniDLNA
{
    /**
     * @var     int
     * @Id
     * @Column(type="integer")
     * @GeneratedValue
     */
    protected $id = null;

    /**
     * @var     boolean
     * @Column(type="boolean")
     */
    protected $enabled = false;

    /**
     * @var     string
     * @Column(type="string")
     */
    protected $email = null;


    public function __construct()
    {
        //$this->setGroups(new ArrayCollection());
    }

    /**
     * @return  int
     */
    public function getId()
    {
        return $this->id;
    }

    /**
     * @param   int     $id
     * @return  void
     */
    public function setId($id)
    {
        $this->id = $id;
    }

    /**
     * @return  string
     */
    public function getEnabled()
    {
        return $this->enabled;
    }

    /**
     * @param   string  $username
     * @return  void
     */
    public function setEnabled($enabled)
    {
        $this->enabled = $enabled;
    }

}

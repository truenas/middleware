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
     * @var     boolean
     * @Column(type="boolean")
     */
    protected $debug = false;

    /**
     * @var     boolean
     * @Column(type="boolean")
     */
    protected $inotify = true;

    /**
     * @var     string
     * @Column(type="string")
     */
    protected $media_dir = null;

    /**
     * @var     integer
     * @Column(type="integer")
     */
    protected $port = 8200;

    /**
     * @var     integer
     * @Column(type="integer")
     */
    protected $notify_interval = 895;

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

    /**
     * @return  string
     */
    public function getInotify()
    {
        return $this->inotify;
    }

    /**
     * @param   string  $inotify
     * @return  void
     */
    public function setInotify($inotify)
    {
        $this->inotify = $inotify;
    }

    /**
     * @return  string
     */
    public function getMediaDir()
    {
        return $this->media_dir;
    }

    /**
     * @param   string  $username
     * @return  void
     */
    public function setMediaDir($mediadir)
    {
        $this->media_dir = $mediadir;
    }

    /**
     * @return  integer
     */
    public function getPort()
    {
        return $this->port;
    }

    /**
     * @param   integer  $username
     * @return  void
     */
    public function setPort($port)
    {
        $this->port = $port;
    }

    /**
     * @return  integer
     */
    public function getNotifyInterval()
    {
        return $this->notify_interval;
    }

    /**
     * @param   integer  $notify_interval
     * @return  void
     */
    public function setNotifyInterval($notify_interval)
    {
        $this->notify_interval = $notify_interval;
    }

}

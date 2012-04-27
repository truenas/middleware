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
     * @var     boolean
     * @Column(type="boolean")
     */
    protected $tivo = false;

    /**
     * @var     boolean
     * @Column(type="boolean")
     */
    protected $rescan = false;

    /**
     * @var     boolean
     * @Column(type="boolean")
     */
    protected $strict_dlna = false;

    /**
     * @var     string
     * @Column(type="string")
     */
    protected $media_dir = null;

    /**
     * @var     string
     * @Column(type="string")
     */
    protected $friendly_name = null;

    /**
     * @var     string
     * @Column(type="string")
     */
    protected $model_number = null;

    /**
     * @var     string
     * @Column(type="string")
     */
    protected $serial = null;

    /**
     * @var     text
     * @Column(type="text")
     */
    protected $auxiliary = null;

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
     * @return  boolean
     */
    public function getInotify()
    {
        return $this->inotify;
    }

    /**
     * @param   boolean  $inotify
     * @return  void
     */
    public function setInotify($inotify)
    {
        $this->inotify = $inotify;
    }

    /**
     * @return  boolean
     */
    public function getTivo()
    {
        return $this->tivo;
    }

    /**
     * @param   boolean  $tivo
     * @return  void
     */
    public function setTivo($tivo)
    {
        $this->tivo = $tivo;
    }

    /**
     * @return  boolean
     */
    public function getRescan()
    {
        return $this->rescan;
    }

    /**
     * @param   boolean  $rescan
     * @return  void
     */
    public function setRescan($rescan)
    {
        $this->rescan= $rescan;
    }

    /**
     * @return  boolean
     */
    public function getStrictDLNA()
    {
        return $this->strict_dlna;
    }

    /**
     * @param   boolean  $rescan
     * @return  void
     */
    public function setStrictDLNA($strict_dlna)
    {
        $this->strict_dlna = $strict_dlna;
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
     * @return  string
     */
    public function getFriendlyName()
    {
        return $this->friendly_name;
    }

    /**
     * @param   string  $friendly_name
     * @return  void
     */
    public function setFriendlyName($friendly_name)
    {
        $this->friendly_name = $friendly_name;
    }

    /**
     * @return  string
     */
    public function getModelNumber()
    {
        return $this->model_number;
    }

    /**
     * @param   string  $model_number
     * @return  void
     */
    public function setModelNumber($model_number)
    {
        $this->model_number = $model_number;
    }

    /**
     * @return  string
     */
    public function getSerial()
    {
        return $this->serial;
    }

    /**
     * @param   string  #serial
     * @return  void
     */
    public function setSerial($serial)
    {
        $this->serial = $serial;
    }

    /**
     * @return  string
     */
    public function getAuxiliary()
    {
        return $this->auxiliary;
    }

    /**
     * @param   string  $auxiliary
     * @return  void
     */
    public function setAuxiliary($auxiliary)
    {
        $this->auxiliary = $auxiliary;
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

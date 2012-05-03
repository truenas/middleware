<?php

// Define path to application directory
defined('APPLICATION_PATH')
    || define('APPLICATION_PATH', realpath(dirname(__FILE__) . '/../../application'));

// Define application environment
defined('APPLICATION_ENV')
    || define('APPLICATION_ENV', (getenv('APPLICATION_ENV') ? getenv('APPLICATION_ENV') : 'development'));

echo APPLICATION_PATH.'\n'. realpath(APPLICATION_PATH . '/../library');

// Ensure library/ is on include_path
set_include_path(implode(PATH_SEPARATOR, array(
    realpath(APPLICATION_PATH . '/../library'),
    get_include_path(),
)));

set_include_path(implode(PATH_SEPARATOR, array(
    realpath(APPLICATION_PATH . '/../../../share/ZendFramework/library'),
    get_include_path(),
)));

require_once 'Zend/Application.php';

// Create application, bootstrap, and run
$application = new Zend_Application(
    APPLICATION_ENV,
    APPLICATION_PATH . '/configs/application.ini'
);
$application->bootstrap();


// * @var Doctrine\ORM\EntityManager $entityManager
$entityManager = Zend_Registry::get('em');
$helperSet = new \Symfony\Component\Console\Helper\HelperSet(
                 array('db' => new \Doctrine\DBAL\Tools\Console\Helper\ConnectionHelper($entityManager->getConnection()),
                       'em' => new \Doctrine\ORM\Tools\Console\Helper\EntityManagerHelper($entityManager)));

\Doctrine\ORM\Tools\Console\ConsoleRunner::run($helperSet);
?>

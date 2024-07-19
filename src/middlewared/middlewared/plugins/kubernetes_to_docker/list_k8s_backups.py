from middlewared.service import Service


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'

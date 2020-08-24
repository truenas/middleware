from middlewared.service import private, Service


class KubernetesService(Service):

    @private
    def post_start(self):
        # TODO:
        #  We will be tainting node here to make sure pods are not schedule-able / executable
        #  Any kind of migrations will be performed and then finally the taint will be removed from node
        #  so it can run pods
        #  We will also configure multus here after k8s is up and multus service account has been created
        pass

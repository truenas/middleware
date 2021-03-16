TrueNAS CORE/Enterprise/SCALE main source repo
=============

Want to contribute or collaborate? Join our [Slack instance](https://www.ixsystems.com/community/threads/collaborator-community-slack-instance.85717/ "Slack Instance"). 


## IMPORTANT NOTE:  
This is the master branch of freenas, which is used for the creation and testing of TrueNAS CORE / Enterprise and TrueNAS SCALE Nightly builds. Submit Pull Requests here if you want to get changes into the next major release of TrueNAS. To build this source repo, checkout https://github.com/freenas/build for CORE/Enterprise and https://github.com/truenas/truenas-build for SCALE

## Pull Request Instructions / Jenkins Commands

When submitting a pull-request, Jenkins will attempt to verify the changes to ensure it does not break our builds and/or passes QA tests.

Once whitelisted, the following commands may be used to interact with that service:

    "ok to test" to accept this pull request for testing
    "test this please" for a one time test run
    "add to whitelist" to add the author to the whitelist

If the build fails for other various reasons you can rebuild.

    "retest this please" to start a new build
    "retest this please CLEAN" to start a new build, non-incremental


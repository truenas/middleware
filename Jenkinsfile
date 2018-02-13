
githubNotify context: 'continuous-integration/jenkins/pr-head', description: 'Build queued',  status: 'PENDING'

node('FreeNAS-ISO') {
  stage('Checkout') {
    context="continuous-integration/jenkins/"
    context += isPRMergeBuild()?"pr-merge/checkout":"branch/checkout"
    setBuildStatus ("${context}", 'Checking out sources', 'PENDING')
    try {
      checkout scm
    } catch (exc) {
      setBuildStatus ("${context}", 'Checkout failed', 'FAILURE')
      context="continuous-integration/jenkins/pr-head"
      setBuildStatus ("${context}", 'Build testing failed', 'FAILURE')
      throw exc
    }
    setBuildStatus ("${context}", 'Check out completed', 'SUCCESS')
  }
  withEnv(['GH_ORG=freenas','GH_REPO=freenas']) {
    stage('ixbuild') {
      echo 'Starting iXBuild Framework pipeline'
      context="continuous-integration/jenkins/pr-head"
      setBuildStatus ("${context}", 'Starting ixbuild process', 'PENDING')
      try {
        sh '/ixbuild/jenkins.sh freenas freenas-pipeline'
      } catch (exc) {
        echo 'Saving failed artifacts...'
        archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
        context="continuous-integration/jenkins/pr-head"
        setBuildStatus ("${context}", 'Build testing failed', 'FAILURE')
        throw exc
      }
    }
    stage('artifact') {
      context="continuous-integration/jenkins/pr-head"
      setBuildStatus ("${context}", 'Artifacting Build', 'PENDING')
      archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
      junit 'results/**'
      setBuildStatus ("${context}", 'Build testing successful!', 'SUCCESS')
    }
  }
}


def isPRMergeBuild() {
    return (env.BRANCH_NAME ==~ /^PR-\d+$/)
}

def getRepoSlug() {
    tokens = "${env.JOB_NAME}".tokenize('/')
    org = tokens[tokens.size()-3]
    repo = tokens[tokens.size()-2]
    return "${org}/${repo}"
}

void setBuildStatus(context, message, state) {
  // partially hard coded URL because of https://issues.jenkins-ci.org/browse/JENKINS-36961, adjust to your own GitHub instance
  step([
      $class: "GitHubCommitStatusSetter",
      contextSource: [$class: "ManuallyEnteredCommitContextSource", context: context],
      reposSource: [$class: "ManuallyEnteredRepositorySource", url: "https://github.com/freenas/${getRepoSlug()}"],
      errorHandlers: [[$class: "ChangingBuildStatusErrorHandler", result: "UNSTABLE"]],
      statusResultSource: [ $class: "ConditionalStatusResultSource", results: [[$class: "AnyBuildResult", message: message, state: state]] ]
  ]);
}


pipeline {

  context="continuous-integration/jenkins/"
  context += isPRMergeBuild()?"pr-merge/checkout":"branch/checkout"
  setBuildStatus ("${context}", 'Build is queued', 'PENDING')

  agent {
    label 'FreeNAS-ISO'
  }
  environment {
    GH_ORG = 'freenas'
    GH_REPO = 'freenas'
  }
  stages {

    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('ixbuild') {
      post {
        failure {
          echo 'Saving failed artifacts...'
          archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
        }
      }
      steps {
        echo 'Starting iXBuild Framework pipeline'
        sh '/ixbuild/jenkins.sh freenas freenas-pipeline'
      }
    }

    stage('artifact') {
      steps {
        archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
        junit 'results/**'
      }
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

pipeline {
  agent none

  environment {
    GH_ORG = 'freenas'
    GH_REPO = 'freenas'
  }
  stages {

    stage('Queued') {
      agent {
        label 'JenkinsMaster'
      }
      steps {
        echo "Build queued"
      }
    }

    stage('ixbuild') {
      agent {
        label 'FreeNAS-ISO'
      }
      post {
        success {
          archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
          junit 'results/**'
        }
        failure {
          echo 'Saving failed artifacts...'
          archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
        }
      }
      steps {
        checkout scm
        echo 'Starting iXBuild Framework pipeline'
        sh '/ixbuild/jenkins.sh freenas freenas-pipeline'
      }
    }
  }
}

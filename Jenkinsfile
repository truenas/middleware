
pipeline {
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

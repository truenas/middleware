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
	  stash includes: 'artifacts/iso/*.iso', name: 'iso'
	  stash includes: 'artifacts/*-Update/**', name: 'update-files'
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

    stage('PR Staging') {
      agent {
        label 'FreeNAS-Update-Stage'
      }
      steps {
        echo 'Staging the PR update'
        unstash 'update-files'
        sh '/root/freenas-update/release-pr-workspace.sh'
      }
    }

    stage('API testing') {
      agent {
        label 'FreeNAS-QA'
      }
      post {
        always {
          junit 'tests/results/*.xml'
        }
      }
      steps {
        echo 'Starting QA API testing'
        unstash 'iso'
        sh 'rm -rf ${WORKSPACE}/tests/iso'
        sh 'mkdir -p ${WORKSPACE}/tests/iso'
        sh 'mv artifacts/iso/*.iso ${WORKSPACE}/tests/iso/'
        sh 'touch ${WORKSPACE}/tests/iso/.keepme'
        echo "ISO WORKSPACE: ${WORKSPACE}/tests/iso/"
        sh 'ixautomation --run api-tests --systype freenas'
      }
    }
  }
}

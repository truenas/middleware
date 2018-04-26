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
        label 'FreeNAS-ISO-testing'
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
        sh 'rm -rf ${WORKSPACE}/artifacts/*Update'
        unstash 'update-files'
        sh '/root/freenas-update/release-pr-workspace.sh'
      }
    }

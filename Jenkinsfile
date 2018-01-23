throttle(['FreeNAS']) {
  node('FreeNAS-ISO') {
      stage('Checkout') {
	checkout scm
      }
      withEnv(['GH_ORG=freenas','GH_REPO=freenas']) {
        stage('ixbuild') {
          echo 'Starting iXBuild Framework pipeline'
	  sh '/ixbuild/jenkins.sh freenas freenas-pipeline'
        }
      }
      post {
        always {
            archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
            junit 'results/**'
        }
      }
  }
}

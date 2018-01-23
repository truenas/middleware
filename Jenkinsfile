throttle(['FreeNAS']) {
  node('FreeNAS-ISO') {
      stage('Checkout') {
	checkout scm
      }
      stage('ixbuild') {
        echo 'Starting iXBuild Framework pipeline'
	sh '/ixbuild/jenkins.sh freenas pipeline'
      }
      post {
        always {
            archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
            junit 'results/**'
        }
      }
  }
}

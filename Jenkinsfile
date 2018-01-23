throttle(['FreeNAS']) {
  node('FreeNAS-ISO') {
      stage('Checkout') {
        checkout([
          $class: 'GitSCM',
          branches: scm.branches,
          extensions: scm.extensions + [[$class: 'CloneOption', timeout: 1200]],
          userRemoteConfigs: scm.userRemoteConfigs
        ])
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

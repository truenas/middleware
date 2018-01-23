throttle(['FreeNAS']) {
  node('FreeNAS-ISO') {
      stage('Checkout') {
	checkout([$class: 'GitSCM', branches: [[name: $env.BRANCH_NAME]], doGenerateSubmoduleConfigurations: false, extensions: [[$class: 'CloneOption', depth: 0, noTags: false, reference: '', shallow: false, timeout: 60]], submoduleCfg: [], userRemoteConfigs: [[url: 'https://github.com/freenas/freenas.git']]])
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

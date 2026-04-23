pipeline {
  agent any

  environment {
    COMPOSE_FILE = 'docker-compose.yml'
  }

  stages {
    stage('Parse Commit Message') {
      steps {
        script {
          def commitMessage = sh(returnStdout: true, script: "git log -1 --pretty=%B").trim()
          env.FORCE_REBUILD = commitMessage.contains("FORCE_REBUILD") ? "true" : "false"
          env.FULL_CLEAN = commitMessage.contains("FULL_CLEAN") ? "true" : "false"
        }
      }
    }

    stage('Clean') {
      when {
        expression { return env.FORCE_REBUILD == "true" || env.FULL_CLEAN == "true" }
      }
      steps {
        script {
          def cleanCmd = "docker compose -f ${COMPOSE_FILE} down --remove-orphans"
          if (env.FULL_CLEAN == "true") {
            cleanCmd += " --rmi local"
          }
          sh "${cleanCmd} || true"
        }
      }
    }

    stage('Deploy') {
      steps {
        script {
          def buildCmd = "docker compose -f ${COMPOSE_FILE} build"
          if (env.FORCE_REBUILD == "true") {
            buildCmd += " --no-cache"
          }
          sh buildCmd
        }
        script {
          def projectId = params.INFISICAL_PROJECT_ID?.trim()
          if (projectId) {
            withCredentials([
              string(credentialsId: 'infisical-client-id',     variable: 'INFISICAL_CLIENT_ID'),
              string(credentialsId: 'infisical-client-secret', variable: 'INFISICAL_CLIENT_SECRET')
            ]) {
              sh """
                INFISICAL_TOKEN=\$(INFISICAL_DISABLE_UPDATE_CHECK=true \
                  INFISICAL_API_URL=https://infisical.nexttech.com.ar/api \
                  infisical login --method=universal-auth \
                    --client-id="\$INFISICAL_CLIENT_ID" \
                    --client-secret="\$INFISICAL_CLIENT_SECRET" \
                    --plain --silent)
                INFISICAL_API_URL=https://infisical.nexttech.com.ar/api \
                INFISICAL_TOKEN="\$INFISICAL_TOKEN" \
                INFISICAL_DISABLE_UPDATE_CHECK=true \
                infisical run --env prod --projectId ${projectId} \
                  -- docker compose -f ${COMPOSE_FILE} up -d
              """
            }
          } else {
            sh "docker compose -f ${COMPOSE_FILE} up -d"
          }
        }
      }
    }
  }
}

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
          if (env.INFISICAL_PROJECT_ID?.trim() && env.INFISICAL_TOKEN?.trim()) {
            def envFlag = env.INFISICAL_ENV?.trim() ?: 'prod'
            sh "INFISICAL_API_URL=https://infisical.nexttech.com.ar/api infisical run --env ${envFlag} --projectId ${env.INFISICAL_PROJECT_ID} -- docker compose -f ${COMPOSE_FILE} up -d"
          } else {
            sh "docker compose -f ${COMPOSE_FILE} up -d"
          }
        }
      }
    }
  }
}

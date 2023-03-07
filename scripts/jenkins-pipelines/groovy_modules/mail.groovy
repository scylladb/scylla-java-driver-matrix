def setMailParameters (Map args) {
	// Parameters:
	// boolean (default false): dryRun - Run builds on dry run so mail to caller only / releng.
	// boolean (default false): debugMail - On debug build  mail to caller only / releng.
	// String (default branchProperties.stableBranchName): branch - For mail text
	// String (default generalProperties.devMail): devAddress - address to send mail to

	general.traceFunctionParams ("mail.setMailParameters", args)
	boolean dryRun = args.dryRun ?: false
	boolean debugMail = args.debugMail ?: false
	String branch = args.branch ?: branchProperties.stableBranchName
	String devAddress = args.devAddress ?: generalProperties.devMail

	if (branchProperties.productName.contains("manager")) {
		devAddress = "${generalProperties.mgmtMail}, ${generalProperties.relengTeam}"
	}

	def logText = "Check console output at ${env.BUILD_URL}\n"

	def qaAddress = generalProperties.qaMail
	def relengAddress = generalProperties.relengMail
	def debugMailAddress

	(runningUserID,runningUserEmail) = setRunningUserInfo ()

	boolean dryOrDebugRun = dryRun || debugMail
	String dryOrDebugText = ""

	if (dryOrDebugRun || JOB_NAME.contains(generalProperties.relengJobPath)) {
		dryOrDebugText = " (dry run or debug build)"
		if ("${runningUserEmail}" == "jenkins") {
			debugMailAddress = generalProperties.debugMail
		} else {
			debugMailAddress = "${runningUserEmail}"
		}
		devAddress = debugMailAddress
		qaAddress = debugMailAddress
		relengAddress = debugMailAddress
	}
	def jobTitle = "Build Job '${env.JOB_NAME} [${env.BUILD_NUMBER}] on branch/release $branch $dryOrDebugText"

	echo "Running build |$JOB_NAME| # |$BUILD_NUMBER|$dryOrDebugText"
	echo "pwd is |${pwd()}|, workspace is |$WORKSPACE|, Node: |$NODE_NAME|, ran by |$runningUserID|"
	echo "Mail will be sent to QA: $qaAddress dev: $devAddress, releng: $relengAddress"

	return [ "${jobTitle}", "${logText}", "${runningUserID}", devAddress, relengAddress, qaAddress ]
}

def setRunningUserInfo () {
	def buildCause = currentBuild.getBuildCauses()
	String strBuildCause = buildCause.toString()
	String runningUserID
	String runningUserEmail
	echo "Build cause: |$strBuildCause|"

	if (strBuildCause.contains("Started by user")) {
		//[[_class:hudson.model.Cause$UserIdCause, shortDescription:Started by user Hagit Segev, userId:hagitsegev, userName:Hagit Segev]]
		echo "This is a user requested build. get username"
		// The wrap fails in case the build was triggered by an scm change / timer.
		wrap([$class: 'BuildUser']) {
			 // https://wiki.jenkins-ci.org/display/JENKINS/Build+User+Vars+Plugin variables available inside this block
			 runningUserID = "${BUILD_USER_ID}"
			 runningUserEmail = BUILD_USER_EMAIL
		}
	} else {
		runningUserID = "jenkins"
		runningUserEmail = "jenkins"
	}
	return [ "${runningUserID}", runningUserEmail ]
}

def mailIfError (String address = "releng@scylladb.com", String title = "Failed Build Results", String body = "Please see the logs on jenkins") {
	echo "Mailing error (if failure / aborted / unstable) build status to ${address}"
	if (currentBuild.currentResult == "ABORTED" || currentBuild.currentResult == "FAILURE" || currentBuild.currentResult == "UNSTABLE") {
		mail (
			to: "$address",
			subject: "$title",
			body: "$body"
		)
	}
}

def mailFixed (String address = generalProperties.devMail, String title = "Fixed Build Results", String body = "Please see the logs on jenkins") {
	echo "Mailing fixed build status to $address"
	mail (
		to: "$address",
		subject: "$title",
		body: "$body"
	)
}

def mailResults (String address = generalProperties.devMail, String title = "Build results", String body = "Please see the logs on jenkins") {
	echo "Mailing build status to $address"
	mail (
		to: "$address",
		subject: "$title",
		body: "$body"
	)
}

def mailWithFileOnBody (Map args) {
	// Parameters:
	// String (default generalProperties.relengMail): address - address to send mail to
	// String (default "Build results"): title - mail subject
	// String (default "Please see the logs on jenkins"): inputBody - mail body
	// String (default WORKSPACE): attachDir - Dir of file to attach
	// String (mandatory) attachFile - file to put on body

	general.traceFunctionParams ("mail.mailWithFileOnBody", args)
	String address = args.address ?: generalProperties.relengMail
	String title = args.title ?: "Build results"
	String inputBody = args.inputBody ?: "Please see the logs on jenkins"
	String attachDir = args.attachDir ?: WORKSPACE

	general.errorMissingMandatoryParam ("mail.mailWithFileOnBody", [attachFile: "$args.attachFile"])

	echo "Mailing to $address"
	def body
	dir(attachDir) {
		def exists = fileExists args.attachFile

		if (exists) {
			body = readFile args.attachFile
		} else {
			body = "Warning: File to put in mail |$args.attachFile| does not exist on |$attachDir|"
		}

		mail (
			to: "$address",
			subject: "$title",
			body: "${inputBody}\n${body}"
		)
	}
}

def mailWithAttachedFile (Map args) {
	// Parameters:
	// String (default generalProperties.relengMail): address - address to send mail to
	// String (default "Build results"): title - mail subject
	// String (default "Please see the logs on jenkins"): inputBody - mail body
	// String (default WORKSPACE): attachDir - Dir of file to attach
	// String (mandatory) attachFile - file to attach

	// I can't call the trace function as fails when the body contains new lines
	//general.traceFunctionParams ("mail.mailWithAttachedFile", args)

	String address = args.address ?: generalProperties.relengMail
	String title = args.title ?: "Build results"
	String inputBody = args.inputBody ?: "Please see the logs on jenkins"
	String attachDir = args.attachDir ?: WORKSPACE

	general.errorMissingMandatoryParam ("mail.mailWithAttachedFile", [attachFile: "$args.attachFile"])

	String missingFileWarning = ""
	dir(attachDir) {
		def exists = fileExists args.attachFile

		if (!exists) {
			missingFileWarning = "Warning: File to attach |$args.attachFile| does not exist on |$attachDir|"
		}

		emailext (
			to: address,
			subject: title,
			body: "${inputBody}\n${missingFileWarning}",
			attachmentsPattern: args.attachFile
		)
	}
}

def committerEmailAddress (String gitCommitStart, String gitCommitEnd, String baseDir = WORKSPACE, debugMail = false) {
	dir(baseDir) {
		if (!git.shaValue(gitCommitStart)) {
			gitCommitStart = git.gitRevParse("origin/${gitCommitStart}")
		}
		if (!git.shaValue(gitCommitEnd)) {
			gitCommitEnd = git.gitRevParse("origin/${gitCommitEnd}")
		}
		if (debugMail) {
			(runningUserID,runningUserEmail) = setRunningUserInfo ()
			return runningUserEmail
		} else {
			listCommittersEmail = sh(script: "git log --pretty=format:\"%ae\" $gitCommitStart...$gitCommitEnd | grep \"@scylladb.com\" | sort -u", returnStdout: true).trim()
			return listCommittersEmail
		}
	}
}

return this

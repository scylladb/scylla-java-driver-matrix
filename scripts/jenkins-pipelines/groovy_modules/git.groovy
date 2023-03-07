def doCheckout (String gitURL = gitProperties.scyllaRepoUrl, String branch = branchProperties.stableBranchName, boolean disableSubmodulesParam = false) {
	println "doCheckout: Checkout git repo: |" + gitURL + "| branch: |$branch| pwd: |${pwd()}|, workspace: |$WORKSPACE| disable submodule param: |$disableSubmodulesParam| (should be true for pkg)"
	// mirror.git is updated daily with clones of all our repositories
	// by the git-mirror job
	def ref_repo = "${env.HOME}/mirror.git"
	if (!fileExists(ref_repo)) {
		ref_repo = ""
	}

	/* CHECKOUT_PULL_REQUEST is used by scylla-ci pipeline which checkout a given PR */
	String refspec = "+refs/heads/$branch:refs/remotes/origin/$branch"
	if (env.CHECKOUT_PULL_REQUEST && gitURL == gitProperties.scyllaRepoUrl) {
	    refspec = "+refs/pull/$branch/head:refs/remotes/origin/$branch"
	}

	checkout([
		$class: 'GitSCM',
		branches: [[name: branch]],
		extensions: [[
			$class: 'SubmoduleOption',
			disableSubmodules: disableSubmodulesParam,
			parentCredentials: true,
			recursiveSubmodules: true,
			reference: ref_repo,
			timeout: 60,
			trackingSubmodules: false
		],[
			$class: 'CloneOption',
			reference: ref_repo,
			timeout: 60
		],[
			$class: 'CheckoutOption',
			timeout: 60
		]],
		submoduleCfg: [],
		userRemoteConfigs: [[
			url: gitURL,
			refspec: "${refspec}",
			credentialsId: 'github-promoter'
		]]
	])
}

boolean shaValue(String value) {
	if (value =~ /^[0-9a-f]+$/) {
		echo "|$value| is a sha"
		return true
	} else {
		echo "|$value| is not a sha"
		return false
	}
}

def checkoutToDir(String gitURL = gitProperties.scyllaRepoUrl, String branch = branchProperties.stableBranchName, String checkoutDir = WORKSPACE, boolean disableSubmodulesParam = false) {
	println "checkoutToDir: Checkout git repo: |" + gitURL + "| branch: |$branch| dir: |$checkoutDir| disableSubmodulesParam: |$disableSubmodulesParam|"
	boolean dirExists = fileExists checkoutDir
	if (! dirExists) {
		echo "Creating dir |${checkoutDir}| for checking out"
		sh "mkdir ${checkoutDir}"
	}

	def sha = ""
	dir (checkoutDir) {
		doCheckout(gitURL, branch, disableSubmodulesParam)
		sh "git status"
		if (shaValue(branch)) {
			sha = branch
		} else {
			sha = gitRevParse("origin/${branch}")
		}
		echo "Sha is: |$sha|"
		return sha
	}
}

String gitRevParse (String branch) {
	def sha = sh(returnStdout: true, script: "git rev-parse ${branch}").trim()
	return sha
}

def cleanWorkSpaceUponRequest(boolean preserveWorkSpace = false) {
	echo "Cleaning workspace |$WORKSPACE|, Node: |$NODE_NAME|"
	if (preserveWorkSpace) {
		echo "Keeping workspace due to user request"
	} else {
		def architecture = sh(returnStdout: true, script: "uname -m").trim()
		echo "architecture: |$architecture| (could be x86_64 or aarch64)"
		if (architecture.toString().contains("aarch64")) {
			echo "This is an ARM machine, can't use sudo to clean root files"
		} else {
			// In order to clean also root owned files, first change ownership
			// https://issues.jenkins-ci.org/browse/JENKINS-24440?focusedCommentId=357010&page=com.atlassian.jira.plugin.system.issuetabpanels%3Acomment-tabpanel#comment-357010
			sh "sudo chmod -R 777 ."
		}
		cleanWs() /* clean up our workspace */
		sh '''
		    if which docker; then
		        docker system prune -a -f --filter until=72h
		    fi
		    if which podman; then
		        buildah rm --all
		        podman system prune -a -f --filter until=72h
		    fi
		'''
	}
}

def createGitProperties(String repoString = branchProperties.gitRepositories, String fileName = generalProperties.gitPropertiesFileName) {
	echo "Creating $fileName file"
	sh "touch $fileName"
	ArrayList repoList = repoString.split('\\,')
	repoList.each { repo ->
		ArrayList namePartsList = repo.split('\\-')
		def repo4PropertyName = namePartsList[0]
		for (i = 1; i < namePartsList.size(); i++) {
			if (!(namePartsList[i].contains("enterprise"))) {
				def capWord = namePartsList[i].capitalize()
				repo4PropertyName = "${repo4PropertyName}${capWord}"
			}
		}

		def repo4Dir = repo.replace("scylla-enterprise", "scylla")
		sh "echo \"${repo4PropertyName}RepoUrl=${generalProperties.gitBaseURL}${repo}.git\" >> ${fileName}"
		if (repo4Dir == "scylla-cassandra-unit-tests") {
			sh "echo \"${repo4PropertyName}CheckoutDir=cassandra-unit-tests\" >> ${fileName}"
		} else {
			sh "echo \"${repo4PropertyName}CheckoutDir=${repo4Dir}\" >> ${fileName}"
		}
	};
}

return this

def getArtifact (Map args) {
	// get artifacts from jenkins or cloud

	// Parameters:
	// boolean (default false): downloadFromCloud - Whether to publish to cloud storage (S3) or not.
	// boolean (default false): ignoreMissingArtifact - whether to ignore error if file is missing
	// boolean (default false): recursiveCloudCopy - whether to copy recursive tree
	// String (default: WORKSPACE): targetPath where to put the downloaded the artifacts.
	// String (mandatory if downloadFromCloud is false): artifactSourceJob From where to download the artifacts.
	// String (mandatory if downloadFromCloud is false): artifactSourceJobNum (number) to download from
	// String (mandatory if downloadFromCloud): sourceUrl - From where to download the artifacts.
	// String (mandatory): artifact - The Needed artifact.

	general.traceFunctionParams ("artifact.getArtifact", args)

	boolean ignoreMissingArtifact = args.ignoreMissingArtifact ?: false
	boolean downloadFromCloud = args.downloadFromCloud ?: false
	boolean recursiveCloudCopy = args.recursiveCloudCopy ?: false
	String targetPath = args.targetPath ?: WORKSPACE

	def mandatoryArgs = general.setMandatoryList (downloadFromCloud, [artifact: "$args.artifact", sourceUrl: "$args.sourceUrl"], [artifact: "$args.artifact", artifactSourceJob: "$args.artifactSourceJob"])
	general.errorMissingMandatoryParam ("artifact.getArtifact", mandatoryArgs)

	if (downloadFromCloud) {
		echo "Download artifacts from cloud"
		String url = general.addTrailingSlashIfMissing(args.sourceUrl)
		url = general.removeHttpsFromUrl(url)
		url = general.addS3PrefixIfMissing(url)

		String fullUrl = "$url${args.artifact}"
		echo "Download $fullUrl to $targetPath/$args.artifact"
		withCredentials([string(credentialsId: 'jenkins2-aws-secret-key-id', variable: 'AWS_ACCESS_KEY_ID'),
		string(credentialsId: 'jenkins2-aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')]) {
			def lsStatus = sh (
				script: "aws s3 ls $fullUrl --recursive",
				returnStdout: true
			).trim()
		}
		if (ignoreMissingArtifact && lsStatus) {
			echo "Could not find artifact on S3. Ignoring as user request"
		} else {
			boolean recursiveFlag = false
			if (recursiveCloudCopy) {
				recursiveFlag = true
			}

			aws.copy (
					recursive: recursiveFlag,
					cpSource: fullUrl,
					cpTarget: "$targetPath/$args.artifact",
					description: "Copy artifact $fullUrl from cloud storage to local dir $args.artifact"
				)
				general.lsPath (targetPath, "content after getting artifacts from cloud")
		}
	} else {
		echo "Download artifacts from Jenkins"
		general.errorMissingMandatoryParam ("artifact.getArtifact download from jenkins:", [artifactSourceJobNum: "$args.artifactSourceJobNum"])
		step([  $class: 'CopyArtifact',
			filter: "${args.artifact}",
			fingerprintArtifacts: true,
			projectName: "${args.artifactSourceJob}",
			selector: [$class: 'SpecificBuildSelector', buildNumber: "$args.artifactSourceJobNum"],
			target: "${targetPath}",
			optional: "${ignoreMissingArtifact}"
		])
	}
}

def getRelocArtifacts (Map args) {
	// get Scylla package artifacts from cloud
	//
	// Parameters:
	// String (mandatory): cloudUrl - From where to download the artifacts.
	// String (mandatory): buildMode release|debug
	// String (default x86_64): architecture Which architecture to publish x86_64|aarch64
	// String (mandatory): scyllaVersion - Scylla version
	// String (mandatory): scyllaRelease - Scylla release

	general.traceFunctionParams ("artifact.getRelocArtifacts", args)
	general.errorMissingMandatoryParam ("artifact.getRelocArtifacts", [cloudUrl: "$args.cloudUrl",
										buildMode: "$args.buildMode"])

	String cloudUrl = general.addTrailingSlashIfMissing(args.cloudUrl)
	String architecture = args.architecture ?: generalProperties.x86ArchName
	String buildMode = args.buildMode ?: "release"

	def artifactsTargets = [:]

	unifiedPackageName = fetchMetadataValue (
		downloadFromCloud: true,
		cloudUrl: cloudUrl,
		fieldName: "unified-pack-url-${architecture}",
	)
	unifiedPackageName = unifiedPackageName.substring(unifiedPackageName.lastIndexOf('/') + 1)

	if (buildMode == "debug") {
		unifiedPackageName = unifiedPackageName.replace("${generalProperties.generalProductName}", "${generalProperties.generalProductName}-debug")
	}

	target = "$WORKSPACE/${generalProperties.generalProductName}/build/${buildMode}/dist/tar"

	artifactsTargets.unifiedReloc = [artifact: unifiedPackageName, target: target]
	artifactsTargets.metadataFile =   [artifact: generalProperties.buildMetadataFile, target: WORKSPACE]

	artifactsTargets.each { key, val ->
		getArtifact(artifact: val.artifact,
			targetPath: val.target,
			sourceUrl: cloudUrl,
			downloadFromCloud: true,
			ignoreMissingArtifact: false,
		)
	}
	publishMetadataFile ()
	general.lsPath (WORKSPACE, "content after getting artifacts of relocatable packages")
	return [target, unifiedPackageName]
}

String relocUnifiedPackageName (Map args) {
	// returns Scylla unified package name on cloud
	// Assuming a package naming convention: "${package name}-${build mode not on release}-${optional architecture}-package.tar.gz"
	// Parameters:
	// boolean (default false): dryRun - Run builds on dry run (that will show commands instead of really run them).
	// boolean (default false) checkLocal - true to check on local disk, false to check on cloud
	// boolean (default true) mustExist - If must exist - error if not found, else, return ""
	// String (default local): urlOrPath - From where to download the artifacts - local path or a URL.
	// String (default: none): buildMode (release | debug | dev)
	// String (default x86_64): architecture Which architecture to publish x86_64|aarch64


	general.traceFunctionParams ("artifact.relocUnifiedPackageName", args)
	general.errorMissingMandatoryParam ("artifact.relocUnifiedPackageName", [urlOrPath: "$args.urlOrPath"])

	boolean checkLocal = args.checkLocal ?: false
	boolean dryRun = args.dryRun ?: false
	boolean mustExist = args.mustExist != null ? args.mustExist : true
	if (dryRun) {
		mustExist = false
	}
	String buildMode = args.buildMode ?: ""
	String architecture = args.architecture ?: generalProperties.x86ArchName


	unifiedPackageName = fetchMetadataValue (
		local: true,
		cloudUrl: "",
		fieldName: "unified-pack-url-${architecture}",
	)
	unifiedPackageName = unifiedPackageName.substring(unifiedPackageName.lastIndexOf('/') + 1)

	if (buildMode == "debug") {
		unifiedPackageName = unifiedPackageName.replace("${generalProperties.generalProductName}", "${generalProperties.generalProductName}-debug")
	}

	if ((checkLocal && general.fileExistsOnPath(unifiedPackageName, args.urlOrPath)) ||
			(! checkLocal && general.fileExistsOnCloud("${args.urlOrPath}${unifiedPackageName}"))) {
		echo "Found package $unifiedPackageName"
		return unifiedPackageName
	}

	if (mustExist) {
		error ("${unifiedPackageName} not found")
	} else {
		echo "Didn't find any package"
		return ""
	}
}

def publishMetadataFile (String buildMetadataFile = generalProperties.buildMetadataFile, String cloudUrl1 = "", String cloudUrl2 = "") {
	echo "Publish the build's metadata file: $buildMetadataFile"
	boolean flattenDirs = false
	def publishStatus = publishArtifactsStatus(buildMetadataFile, WORKSPACE)
	if (cloudUrl1) {
		publishStatus |= artifact.publishS3Artifact(buildMetadataFile, WORKSPACE, cloudUrl1, flattenDirs)
	}
	if (cloudUrl2) {
		publishStatus |= artifact.publishS3Artifact(buildMetadataFile, WORKSPACE, cloudUrl2, flattenDirs)
	}
	if (publishStatus) {
		error("Could not publish $buildMetadataFile")
	}
}

boolean publishArtifactsStatus (String wildcardFiles = "*.txt", String baseDir = WORKSPACE, String excludeWildcardFiles = "", boolean dryRun = false) {
	// This function gets baseDir as full path or as relative path based on the default dir when you call it.
	// It does cd on the baseDir.
	// The wildcardFiles should be a path, relative to the baseDir (or a file). This path (file) is the path to publihs.
	// So if you give a as baseDir and b/c.txt as File, you will see b/c.txt as the artifact.
	boolean status = false
	echo "Going to archive artifacts (as Jenkins artifacts): |$wildcardFiles| from dir |$baseDir|, excluding |$excludeWildcardFiles|, dryRun: $dryRun"
	if (!dryRun) {
		boolean dirExists = fileExists "$baseDir"
		if (dirExists) {
			dir(baseDir) {
				def files = findFiles(glob: "$wildcardFiles", excludes: "$excludeWildcardFiles")
				boolean exists = files.length > 0
				if (exists) {
					try {
						archiveArtifacts artifacts: "$wildcardFiles", excludes: "$excludeWildcardFiles"
					} catch (error) {
						echo "Error: Could not publish |$wildcardFiles|. Error: |$error|"
						status = true
					}
				} else {
					echo "Nothing to publish. No |$wildcardFiles| under |$baseDir|"
					status = true
				}
			}
		} else {
			echo "Nothing to publish (no baseDir |$baseDir|)"
			status = true
		}
	}
	return status
}

String fetchMetadataValue (Map args) {
	// get a value from metadata file as artifact from jenkins or cloud
	// Download the file if does not exist locally
	//
	// Parameters:
	// boolean (default false): downloadFromCloud - Whether to publish to cloud storage (S3) or not.
	// String (mandatory if downloadFromCloud is false): artifactSourceJob - From where to download the artifacts.
	// String (default: last success run): artifactSourceJobNum (number) to download from
	// String (mandatory if downloadFromCloud): cloudUrl - From where to download the artifacts.
	// String (mandatory): fieldName - Name of field to take value from.
	// String (default: null): fileSuffix - extension for the metadata file name. Used on promotion, as it uses few files)
	// boolean (default: false): local - Get metadata from local or remote

	general.traceFunctionParams ("artifact.fetchMetadataValue", args)

	boolean downloadFromCloud = args.downloadFromCloud ?: false
	String cloudUrl = args.cloudUrl ?: ""
	String fileSuffix = args.fileSuffix ?: ""
	boolean local = args.local ?: false

	def mandatoryArgs = general.setMandatoryList(downloadFromCloud, [cloudUrl: "$args.cloudUrl"], [artifactSourceJob: "$args.artifactSourceJob"])
	general.errorMissingMandatoryParam ("artifact.fetchMetadataValue", mandatoryArgs)

	// FixMe: We should improve this in the future to return a Metadata object that the callers can query.
	String metaDataFileName=generalProperties.buildMetadataFile
	if (fileSuffix) {
		metaDataFileName="${generalProperties.buildMetadataFile}-${fileSuffix}"
	}
	String metaDataFilePath="$WORKSPACE/${metaDataFileName}"
	if (!local) {
		getArtifact(artifact: generalProperties.buildMetadataFile,
			targetPath: WORKSPACE,
			artifactSourceJob: args.artifactSourceJob,
			artifactSourceJobNum: args.artifactSourceJobNum,
			downloadFromCloud: downloadFromCloud,
			sourceUrl: cloudUrl,
			ignoreMissingArtifact: false
		)
		if (fileSuffix) {
			sh "mv ${generalProperties.buildMetadataFile} $metaDataFileName"
		}
	}

	fieldValue = general.runOrDryRunShOutput (false, "grep '$args.fieldName' $metaDataFilePath | awk '{print \$2}'", "Get metadata Value")
	echo "Value of field |$args.fieldName| from metadatafile of job |$args.artifactSourceJob|: |$fieldValue|"
	if (! fieldValue) {
		error ("Could not get $args.fieldName from relocatable metadata file")
	}
	return fieldValue
}

String getLastSuccessfulUrl (Map args) {
	// String (default: empty): artifactWebUrl - URL of reloc or packaging items
	// String (default: empty): artifactSourceJob - base build name (next / build) - from where should the called builds take artifacts
	// String (default: empty): artifactSourceJobNum - number of base job (from where should the called builds take artifacts)
	// String (mandatory): fieldName - Name of field to take value from.

	general.traceFunctionParams ("artifact.getLastSuccessfulUrl", args)
	general.errorMissingMandatoryParam ("artifact.getLastSuccessfulUrl", [fieldName: "$args.fieldName"])

	String artifactWebUrl = args.artifactWebUrl ?: ""
	String artifactSourceJob = args.artifactSourceJob ?: ""
	String artifactSourceJobNum = args.artifactSourceJobNum ?: ""
	String fieldName = args.fieldName ?: ""

	if (!artifactWebUrl || artifactWebUrl == "latest") {
		cloudUrl = artifact.fetchMetadataValue (
			downloadFromCloud: false,
			artifactSourceJob: artifactSourceJob,
			artifactSourceJobNum: artifactSourceJobNum,
			fieldName: fieldName,
		)
	} else {
		cloudUrl = artifactWebUrl
	}
	if (!general.fileExistsOnCloud (cloudUrl)) {
		error("artifact.getLastSuccessfulUrl: Cloud URL: $cloudUrl does not exist.")
	}
	return cloudUrl
}

return this

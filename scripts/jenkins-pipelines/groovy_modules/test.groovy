def setupTestEnv(String buildMode, String architecture=generalProperties.x86ArchName, boolean dryRun=false, String scyllaVersion, String scyllaRelease) {
	// This override of HOME as an empty dir is needed by ccm
	echo "Setting test environment, mode: |$buildMode|, architecture: |$architecture|"
	def homeDir="$WORKSPACE/cluster_home"
	createEmptyDir(homeDir)
	unifiedPackageName = artifact.relocUnifiedPackageName (
		dryRun: dryRun,
		checkLocal: true,
		mustExist: false,
		urlOrPath: "$WORKSPACE/${gitProperties.scyllaCheckoutDir}/build/$buildMode/dist/tar",
		buildMode: buildMode,
		architecture: architecture,
	)

	String scyllaUnifiedPkgFile = "$WORKSPACE/${gitProperties.scyllaCheckoutDir}/build/$buildMode/dist/tar/${unifiedPackageName}"
	echo "Test will use package: $scyllaUnifiedPkgFile"
	boolean pkgFileExists = fileExists scyllaUnifiedPkgFile
	env.NODE_INDEX = generalProperties.smpNumber
	env.SCYLLA_VERSION = artifactScyllaVersion()
	if (!env.MAPPED_SCYLLA_VERSION && !general.versionFormatOK(env.SCYLLA_VERSION)) {
		env.MAPPED_SCYLLA_VERSION = "999.99.0"
	}
	env.EVENT_LOOP_MANAGER = "asyncio"
	// Some tests need event loop, 'asyncio' is most tested, so let's use it
	env.SCYLLA_UNIFIED_PACKAGE = scyllaUnifiedPkgFile
	env.DTEST_REQUIRE = "${branchProperties.dtstRequireValue}" // Could be empty / not exist
}

def createEmptyDir(String path) {
	sh "rm -rf $path && mkdir -p $path"
}

def artifactScyllaVersion() {
	def versionFile = generalProperties.buildMetadataFile
	def scyllaSha = ""
	boolean versionFileExists = fileExists "${versionFile}"
	if (versionFileExists) {
		scyllaSha = sh(script: "awk '/scylladb\\/scylla(-enterprise)?\\.git/ { print \$NF }' ${generalProperties.buildMetadataFile}", returnStdout: true).trim()
	}
	echo "Version is: |$scyllaSha|"
	return scyllaSha
}

def doJavaDriverMatrixTest(Map args) {
	// Run the Java test upon different repos
	// Parameters:
	// boolean (default false): dryRun - Run builds on dry run (that will show commands instead of really run them).
	// string (mandatory): datastaxJavaDriverCheckoutDir - Scylla or datastax checkout dir
	// String (mandatory): javaDriverVersions -
	// String (mandatory): driverType - scylla || datastax
	// String (default: x86_64): architecture Which architecture to publish x86_64|aarch64
	// String (mandatory): scyllaVersion - Scylla version
	// String (mandatory): scyllaRelease - Scylla release

	general.traceFunctionParams ("test.doJavaDriverMatrixTest", args)
	general.errorMissingMandatoryParam ("test.doJavaDriverMatrixTest",
		[datastaxJavaDriverCheckoutDir: "$args.datastaxJavaDriverCheckoutDir",
		 javaDriverVersions: "$args.javaDriverVersions",
		 scyllaVersion: "$args.scyllaVersion",
		 scyllaRelease: "$args.scyllaRelease",
		])

	boolean dryRun = args.dryRun ?: false
	String architecture = args.architecture ?: generalProperties.x86ArchName
	String scyllaVersion = args.scyllaVersion
	String scyllaRelease = args.scyllaRelease

	setupCassandraResourcesDir()
	setupTestEnv("release", architecture, dryRun, scyllaVersion, scyllaRelease)
	String pythonParams = "python3 main.py $WORKSPACE/$args.datastaxJavaDriverCheckoutDir "

	pythonParams += "--versions '$args.javaDriverVersions' --scylla-version ${env.SCYLLA_VERSION} --driver-type $args.driverType --version-size 2"
	if (args.email_recipients?.trim()) {
	    pythonParams += " --recipients $args.email_recipients"
	}
	dir("$WORKSPACE/${gitProperties.scyllaJavaDriverMatrixCheckoutDir}") {
		general.runOrDryRunSh (dryRun, "$WORKSPACE/${gitProperties.scyllaJavaDriverMatrixCheckoutDir}/scripts/run_test.sh $pythonParams", "Run Java Driver Matrix test")
	}
}

def setupCassandraResourcesDir() {
	// This empty dir and ln are needed by ccm
	String cassandraResourcesDir="$WORKSPACE/${gitProperties.scyllaCheckoutDir}/resources"
	createEmptyDir(cassandraResourcesDir)
	sh "ln -s $WORKSPACE/${gitProperties.scyllaToolsJavaCheckoutDir} $cassandraResourcesDir/cassandra"
}

return this

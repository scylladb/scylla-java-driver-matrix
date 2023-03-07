def copy(Map args) {
	// Run AWS S3 cp command
	//
	// Parameters:
	// boolean (default false): dryRun - Run builds on dry run (that will show commands instead of really run them).
	// boolean (default false): recursive - recursive flag
	// String (mandatory): cpSource - The AWS S3 cp source
	// String (mandatory): cpTarget - The AWS S3 command cp target
	// String (default: none) excludeItems - Comma separated items to exclude
	// String (default: copy source to destination): description - Text describes what you are doing

	general.traceFunctionParams ("aws.copy", args)
	general.errorMissingMandatoryParam ("aws.copy",
		[cpSource: "$args.cpSource",
		 cpTarget: "$args.cpTarget",
		]
	)

	boolean dryRun = args.dryRun ?: false
	boolean recursive = args.recursive ?: false
	String excludeItems = args.excludeItems ?: ""
	String description = args.description ?: "AWS S3 copy of $args.cpSource to $args.cpTarget"

	aws.runOrDryRunS3Cmd (
		dryRun: dryRun,
		baseCmd: generalProperties.awsS3CpCommand,
		recursive: recursive,
		excludeItems: excludeItems,
		cmdArtifacts: "$args.cpSource $args.cpTarget",
		description: description
	)
}

def remove(Map args) {
	// Run AWS S3 cp command
	//
	// Parameters:
	// boolean (default false): dryRun - Run builds on dry run (that will show commands instead of really run them).
	// boolean (default false): recursive - recursive flag
	// String (mandatory): rmItem - The AWS S3 item to remove
	// String (default: none) excludeItems - Comma separated items to exclude
	// String (default: remove item from S3): description - Text describes what you are doing

	general.traceFunctionParams ("aws.remove", args)
	general.errorMissingMandatoryParam ("aws.remove",
		[cpSource: "$args.rmItem"]
	)

	boolean dryRun = args.dryRun ?: false
	boolean recursive = args.recursive ?: false
	String excludeItems = args.excludeItems ?: ""
	String description = args.description ?: "AWS S3 copy of $args.cpSource to $args.cpTarget"

	aws.runOrDryRunS3Cmd (
		dryRun: dryRun,
		baseCmd: generalProperties.awsS3RmCommand,
		recursive: recursive,
		excludeItems: excludeItems,
		cmdArtifacts: args.rmItem,
		description: description,
	)
}

def sync(src, dst, dryrun=false) {
	/**
	 * This function copies/updates files from a source folder to destination.
	 * Source and destination can be LocalPath OR S3Uri (ex. s3://)
	 *
	 * @param 	src		source folder to copy from
	 * @param 	dst		destination folder to copy to
	 * @param 	dryrun	run aws-cli with --dryrun flag
	 */

	general.traceFunctionParams("aws.sync", [src, dst, dryrun])
	general.errorMissingMandatoryParam("aws.sync",
		[src: src, dst: dst]
	)

	aws.runOrDryRunS3Cmd (
		dryRun: dryrun,
		baseCmd: generalProperties.awsS3SyncCommand,
		cmdArtifacts: "${src} ${dst}",
	)
}

def runOrDryRunS3Cmd (Map args) {
	// Run an AWS S3 command
	//
	// Parameters:
	// boolean (default false): dryRun - Run builds on dry run (that will show commands instead of really run them).
	// boolean (default false): recursive - recursive flag
	// String (default: none) excludeItems - Comma separated items to exclude
	// String (mandatory): baseCmd - The AWS S3 command such as rm, cp
	// String (Mandatory) cmdArtifacts - The AWS S3 command artifacts, such as what to copy / rm and other arguments
	// String (Mandatory): description - Text describes what you are doing

	general.traceFunctionParams ("aws.runOrDryRunS3Cmd", args)
	general.errorMissingMandatoryParam ("aws.runOrDryRunS3Cmd",
		[baseCmd: "$args.baseCmd",
		 cmdArtifacts: "$args.cmdArtifacts",
		 description: "$args.description"]
	)

	boolean dryRun = args.dryRun ?: false
	boolean recursive = args.recursive ?: false
	String excludeItems = args.excludeItems ?: ""

	String recursiveFlag = ""
	if (recursive) {
		recursiveFlag = "--recursive"
	}

	String excludeParam = ""
	if (excludeItems) {
		ArrayList items = excludeItems.split('\\,')
		items.each { item ->
			excludeParam += " --exclude $item"
		}
	}

	String cmd = args.baseCmd
	if (dryRun) {
		cmd += " --dryrun"
	}
	cmd += " $args.cmdArtifacts $recursiveFlag $excludeParam"
	if (general.toolInstalled (generalProperties.defaultContainerTool)) {
		env.DPACKAGER_TOOL=generalProperties.defaultContainerTool
		dpackagerAwsCommand = general.setAwsDpackagerCommand ("", "$WORKSPACE/${gitProperties.scyllaPkgCheckoutDir}")
		echo "Running sh cmd: |$cmd| using dpackager"
		sh "$dpackagerAwsCommand -- $cmd"
	} else {
		echo "Running local sh cmd: |$cmd|"
		withCredentials([string(credentialsId: 'jenkins2-aws-secret-key-id', variable: 'AWS_ACCESS_KEY_ID'),
		string(credentialsId: 'jenkins2-aws-secret-access-key', variable: 'AWS_SECRET_ACCESS_KEY')]) {
			sh "$cmd"
		}
	}
}

return this

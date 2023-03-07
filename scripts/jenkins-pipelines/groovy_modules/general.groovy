def runOrDryRunSh (boolean dryRun = false, String cmd, String description) {
    if (dryRun) {
        echo "dry-run - command: $cmd"
    } else {
        sh (script: cmd)
    }
}

boolean fileExistsOnPath(String file, String path=WORKSPACE) {
    boolean exists = fileExists "$path/$file"
    if (exists) {
        echo "File |$file| exists on path |$path|"
        return true
    } else {
        echo "File |$file| does not exist on path |$path|"
        return false
    }
}

boolean versionFormatOK(String versionID) {
    return versionID ==~ /\d+\.\d+\.\d+(\.[a-z0-9]*|)/
}

def runOrDryRunShOutput (boolean dryRun = false, String cmd, String description) {
    def cmdOutput = ""
    if (dryRun) {
        echo "dry-run - command: $cmd"
        cmdOutput = "dry-run"
    } else {
        cmdOutput = sh(script: cmd, returnStdout:true).trim()
    }
    return cmdOutput
}

def lsPath (String path = WORKSPACE, String header = "content") {
    // Show a path/dir content. Usualy to see which artifacts were downloaded (names, size, permissions).
    echo "============= Dir $path $header ==============="
    try {
        sh "ls -la $path"
    } catch (error) {
        echo "path |$path| does not exist"
    }
    echo "===================================================================================="
}

String addTrailingSlashIfMissing(String url) {
    if(url.charAt(url.length()-1)!="/"){
    url += "/"
    }
    return url
}

boolean toolInstalled (String toolCommand){
    installed = true
    try {
        sh "which $toolCommand"
    } catch (error) {
        echo "Could not find the tool $toolCommand Error: $error"
        installed = false
    }
    return installed
}

String addS3PrefixIfMissing(String url) {
    if (! url.contains("s3://")) {
        url = "s3://$url"
    }
    return url
}

String removeHttpsFromUrl (String url) {
    return url.replaceFirst("https://", "")
}

def traceFunctionParams (String functionName, args) {
    Map params = [:]
    args.each{ k, v -> params["${k}"] = "${v}" }
    echo "Call $functionName with: ${params}"
}

def setMandatoryList (boolean mandatoryFlag, def mandatoryIfTrue, def mandatoryIfFalse) {
    def mandatoryArgs = []
    if (mandatoryFlag) {
        mandatoryArgs = mandatoryIfTrue
    } else {
        mandatoryArgs = mandatoryIfFalse
    }
    return mandatoryArgs
}

def errorMissingMandatoryParam (String functionName, args) {
    String missingArgs = ""
    args.each { name, value ->
        if (value == null || value == "") {
            missingArgs += "$name, "
        }
        if (missingArgs) {
            error ("Missing mandatory parameter(s) on $functionName: $missingArgs")
        }
    }
}

String setAwsDpackagerCommand (String dpackagerCommand = "", String pkgCheckoutDir = gitProperties.scyllaPkgCheckoutDir) {
    if (! dpackagerCommand) {
        dpackagerCommand = "$pkgCheckoutDir/${generalProperties.dpackagerPath}"
    }
    dpackagerCommand += ' -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID'
    return dpackagerCommand
}

boolean fileExistsOnCloud(String url) {
    url = general.addS3PrefixIfMissing(url)
    try {
        def lsOutput = general.runOrDryRunShOutput (false, "aws s3 ls $url", "Check if $url exists")
        echo "aws s3 ls output: |$lsOutput|"
        if (lsOutput) {
            echo "URL: |$url| exists."
            return true
        } else {
            echo "URL: |$url| does not exist."
            return false
        }
    } catch (error) {
        echo "URL: |$url| does not exist."
        return false
    }
}

return this
